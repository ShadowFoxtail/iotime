 #!/usr/bin/env python3

import argparse
import os
import pickle
import time
from pathlib import Path
import math
import sys
from datetime import datetime, timezone, timedelta

from astropy.time import Time
from astroquery.jplhorizons import Horizons


# ---------------------------------------------------------------------
# Nexus City canon
# ---------------------------------------------------------------------

NEXUS_NAME = "Nexus City"
NEXUS_LATITUDE = 0.0
NEXUS_LONGITUDE_WEST = 50.0
NEXUS_ELEVATION_KM = 0.0

IO_ID = 501
JUPITER_ID = 599
SUN_ID = 10

GALILEAN_MOONS = {
    "Europa": 502,
    "Ganymede": 503,
    "Callisto": 504,
}


# ---------------------------------------------------------------------
# iotime application settings
# ---------------------------------------------------------------------

IOTIME_VERSION = "1.0.1"

CACHE_DIR = (
    Path.home()
    / ".cache"
    / "iotime"
)

SATELLITE_CACHE_TTL = 10 * 60
ECLIPSE_CACHE_TTL = 10 * 60

CACHE_BYPASS = False
CACHE_HITS = set()

USE_COLOR = (
    sys.stdout.isatty()
    and "NO_COLOR" not in os.environ
)


def ansi(text, code):
    """
    Apply ANSI terminal formatting when color is enabled.
    """
    if not USE_COLOR:
        return text

    return (
        f"\033[{code}m"
        f"{text}"
        "\033[0m"
    )


def heading(text):
    return ansi(text, "1;36")


def section_heading(text):
    return ansi(text, "1;34")


def light_state_style(state):
    if state == "DAY":
        return ansi(state, "1;33")

    if "TWILIGHT" in state:
        return ansi(state, "1;36")

    if state == "NIGHT":
        return ansi(state, "1;34")

    return state


def condition_style(state):
    """
    Color natural light states and Jovian eclipses.
    """
    if "ECLIPSE" in state:
        return ansi(state, "1;31")

    return light_state_style(state)


def status_style(text, status):
    """
    Color a satellite visibility/status field while preserving
    any padding already present in text.
    """
    if status == "VISIBLE":
        code = "1;32"

    elif status == "BELOW HORIZON":
        code = "2"

    elif "OCCULTED" in status:
        code = "1;35"

    elif "TRANSITING" in status:
        code = "1;33"

    elif (
        "SHADOW" in status
        or "ECLIPSE" in status
    ):
        code = "1;34"

    elif "UNKNOWN" in status:
        code = "1;31"

    else:
        code = "1;36"

    return ansi(text, code)


def event_style(text):
    """
    Color upcoming astronomical event descriptions.
    """
    lowered = text.lower()

    if (
        "sunrise" in lowered
        or "sunset" in lowered
    ):
        return ansi(text, "1;33")

    if (
        "dawn" in lowered
        or "twilight" in lowered
    ):
        return ansi(text, "1;36")

    if (
        "behind jupiter" in lowered
        or "crossing jupiter" in lowered
        or "jupiter's shadow" in lowered
    ):
        return ansi(text, "1;35")

    if (
        " rises " in f" {lowered} "
        or " sets " in f" {lowered} "
    ):
        return ansi(text, "1;32")

    return ansi(text, "1;36")


def cache_file_for(key):
    """
    Return the cache filename for a simple safe cache key.
    """
    safe_key = "".join(
        char
        if char.isalnum() or char in "-_"
        else "_"
        for char in key
    )

    return (
        CACHE_DIR
        / f"{safe_key}.pickle"
    )


def cache_load(key, ttl_seconds):
    """
    Load a cached Python object if it is still fresh.
    """
    if CACHE_BYPASS:
        return None

    cache_file = cache_file_for(key)

    try:
        age = (
            time.time()
            - cache_file.stat().st_mtime
        )

        if age > ttl_seconds:
            return None

        with cache_file.open("rb") as handle:
            value = pickle.load(handle)

        CACHE_HITS.add(key)

        return value

    except (
        FileNotFoundError,
        EOFError,
        OSError,
        pickle.PickleError,
    ):
        return None


def cache_store(key, value):
    """
    Store a Python object in iotime's local cache.
    """
    try:
        CACHE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        cache_file = cache_file_for(key)

        with cache_file.open("wb") as handle:
            pickle.dump(
                value,
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    except OSError:
        # Cache failure should never make astronomy fail.
        pass



def horizons_longitude(west_longitude):
    """
    Convert positive west longitude into the eastward value Horizons
    expects for a prograde body such as Io.

    Nexus City:
        50 degrees W

    Horizons:
        50 - 360 = -310 degrees
    """
    return west_longitude - 360.0


NEXUS_LOCATION = {
    "lon": horizons_longitude(NEXUS_LONGITUDE_WEST),
    "lat": NEXUS_LATITUDE,
    "elevation": NEXUS_ELEVATION_KM,
    "body": IO_ID,
}


# ---------------------------------------------------------------------
# Sky interpretation
# ---------------------------------------------------------------------

def sky_condition(sun_elevation):
    if sun_elevation >= 0:
        return "DAY"
    elif sun_elevation >= -6:
        return "CIVIL TWILIGHT"
    elif sun_elevation >= -12:
        return "NAUTICAL TWILIGHT"
    elif sun_elevation >= -18:
        return "ASTRONOMICAL TWILIGHT"
    else:
        return "NIGHT"


def jupiter_phase(illumination, later_illumination):
    waxing = later_illumination > illumination

    if illumination >= 99.5:
        return "Full"

    if illumination <= 0.5:
        return "New"

    if 48 <= illumination <= 52:
        return "First Quarter" if waxing else "Last Quarter"

    if illumination > 52:
        return "Waxing Gibbous" if waxing else "Waning Gibbous"

    return "Waxing Crescent" if waxing else "Waning Crescent"


def eclipse_condition(
    sun_jupiter_separation,
    sun_diameter,
    jupiter_diameter,
):
    """
    Determine whether Jupiter overlaps the Sun.

    Returns:
        TOTAL JOVIAN ECLIPSE
        PARTIAL JOVIAN ECLIPSE
        None
    """
    sun_radius = sun_diameter / 2.0
    jupiter_radius = jupiter_diameter / 2.0

    total_limit = jupiter_radius - sun_radius
    partial_limit = jupiter_radius + sun_radius

    if sun_jupiter_separation <= total_limit:
        return "TOTAL JOVIAN ECLIPSE"

    if sun_jupiter_separation <= partial_limit:
        return "PARTIAL JOVIAN ECLIPSE"

    return None

def angular_separation(az1, el1, az2, el2):
    """
    Calculate the angular distance between two objects in the sky.

    Inputs and result are in degrees.
    """
    az1 = math.radians(az1)
    el1 = math.radians(el1)
    az2 = math.radians(az2)
    el2 = math.radians(el2)

    cos_sep = (
        math.sin(el1) * math.sin(el2)
        + math.cos(el1)
        * math.cos(el2)
        * math.cos(az1 - az2)
    )

    # Protect against tiny floating-point errors.
    cos_sep = max(-1.0, min(1.0, cos_sep))

    return math.degrees(
        math.acos(cos_sep)
    )


def format_apparent_size(degrees):
    """
    Display large objects in degrees and smaller ones in
    arcminutes or arcseconds.
    """
    if degrees >= 1.0:
        return f"{degrees:.2f}°"

    arcminutes = degrees * 60.0

    if arcminutes >= 1.0:
        return f"{arcminutes:.1f}′"

    arcseconds = degrees * 3600.0

    return f"{arcseconds:.1f}″"

def satellite_status(code, elevation):
    """
    Translate the JPL Horizons satellite visibility code
    into a Nexus-friendly description.

    Astroquery normally returns the significant visibility
    character without Horizons' leading slash.
    """
    if elevation < 0:
        return "BELOW HORIZON"

    code = str(code).strip().lstrip("/")

    statuses = {
        "t": "TRANSITING JUPITER",
        "O": "OCCULTED BY JUPITER",
        "p": "PARTIAL ECLIPSE",
        "P": "OCCULTED + PARTIAL ECLIPSE",
        "u": "IN JUPITER'S SHADOW",
        "U": "OCCULTED + IN SHADOW",
        "-": "PRIMARY BODY",
        "*": "VISIBLE",
    }

    return statuses.get(code, f"UNKNOWN ({code})")

def compass_direction(azimuth):
    """
    Convert azimuth into a familiar 8-point compass direction.
    """
    directions = [
        "N", "NE", "E", "SE",
        "S", "SW", "W", "NW",
    ]

    index = round(azimuth / 45.0) % 8
    return directions[index]


def elevation_description(elevation):
    """
    Describe how high an object appears in the sky.
    """
    if elevation < 0:
        return "below horizon"

    if elevation < 10:
        return "very low"

    if elevation < 25:
        return "low"

    if elevation < 50:
        return "mid-sky"

    if elevation < 75:
        return "high"

    return "near overhead"


def parse_nst_timestamp(value):
    """
    Parse a Nexus Standard Time timestamp.

    NST is numerically identical to UTC.

    Accepted forms:
        YYYY-MM-DDTHH:MM
        YYYY-MM-DDTHH:MM:SS
    """
    if value is None:
        return None

    formats = (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
    )

    for fmt in formats:
        try:
            parsed = datetime.strptime(
                value,
                fmt,
            )

            return parsed.replace(
                tzinfo=timezone.utc
            )

        except ValueError:
            pass

    raise ValueError(
        "Invalid NST timestamp. "
        "Use YYYY-MM-DDTHH:MM "
        "or YYYY-MM-DDTHH:MM:SS."
    )


def get_sky(reference_time=None):
    now = (
        reference_time
        if reference_time is not None
        else datetime.now(timezone.utc)
    )

    later = now + timedelta(minutes=30)

    now_jd = Time(now).jd
    later_jd = Time(later).jd

    sun_query = Horizons(
        id=str(SUN_ID),
        location=NEXUS_LOCATION,
        epochs=now_jd,
    )

    sun = sun_query.ephemerides(
        quantities="4,13"
    )[0]

    jupiter_query = Horizons(
        id=str(JUPITER_ID),
        location=NEXUS_LOCATION,
        epochs=[now_jd, later_jd],
    )

    jupiter = jupiter_query.ephemerides(
        quantities="4,10,13,23,24"
    )

    jupiter_now = jupiter[0]
    jupiter_later = jupiter[1]

    return {
        "time": now,

        "sun_azimuth": float(sun["AZ"]),
        "sun_elevation": float(sun["EL"]),
        "sun_diameter_deg":
            float(sun["ang_width"]) / 3600.0,

        "jupiter_azimuth": float(jupiter_now["AZ"]),
        "jupiter_elevation": float(jupiter_now["EL"]),

        "jupiter_illumination":
            float(jupiter_now["illumination"]),

        "jupiter_later_illumination":
            float(jupiter_later["illumination"]),

        "jupiter_diameter_deg":
            float(jupiter_now["ang_width"]) / 3600.0,

        "jupiter_phase_angle":
            float(jupiter_now["alpha"]),

        "sun_jupiter_separation":
            float(jupiter_now["elong"]),
    }

def get_jovian_sky(reference_time=None):
    """
    Retrieve the current apparent positions and visibility
    states of Jupiter, Europa, Ganymede, and Callisto.
    """
    now = (
        reference_time
        if reference_time is not None
        else datetime.now(timezone.utc)
    )
    now_jd = Time(now).jd

    bodies = []

    # Jupiter itself
    query = Horizons(
        id=str(JUPITER_ID),
        location=NEXUS_LOCATION,
        epochs=now_jd,
    )

    row = query.ephemerides(
        quantities="4,13"
    )[0]

    bodies.append({
        "name": "Jupiter",
        "azimuth": float(row["AZ"]),
        "elevation": float(row["EL"]),
        "diameter_deg":
            float(row["ang_width"]) / 3600.0,
        "sat_vis": None,
        "separation_deg": None,
    })

    # Galilean moons visible from Io
    for name, target_id in GALILEAN_MOONS.items():

        query = Horizons(
            id=str(target_id),
            location=NEXUS_LOCATION,
            epochs=now_jd,
        )

        # 4  = azimuth/elevation
        # 12 = separation from Jupiter + visibility code
        # 13 = apparent angular diameter
        row = query.ephemerides(
            quantities="4,12,13"
        )[0]

        bodies.append({
            "name": name,
            "azimuth": float(row["AZ"]),
            "elevation": float(row["EL"]),
            "diameter_deg":
                float(row["ang_width"]) / 3600.0,

            "sat_vis": str(row["sat_vis"]),

            # Horizons reports sat_sep in arcseconds.
            "separation_deg":
                float(row["sat_sep"]) / 3600.0,
        })

    return now, bodies

# ---------------------------------------------------------------------
# Eclipse forecasting
# ---------------------------------------------------------------------

def jd_to_datetime(jd):
    return Time(
        float(jd),
        format="jd",
        scale="utc",
    ).to_datetime(timezone=timezone.utc)


def find_next_eclipse(reference_time=None):
    """
    Search from three hours before the reference time through 48 hours ahead.

    The small look-back allows this to correctly identify the beginning
    of an eclipse if iotime is run while one is already in progress.

    The search is sampled at one-minute intervals.
    """
    now = (
        reference_time
        if reference_time is not None
        else datetime.now(timezone.utc)
    )

    start = now - timedelta(hours=3)
    stop = now + timedelta(hours=48)

    epochs = {
        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "stop": stop.strftime("%Y-%m-%d %H:%M:%S"),
        "step": "1m",
    }

    # Sun:
    #   4  = azimuth/elevation
    #   13 = angular diameter
    sun_query = Horizons(
        id=str(SUN_ID),
        location=NEXUS_LOCATION,
        epochs=epochs,
    )

    sun_table = sun_query.ephemerides(
        quantities="4,13"
    )

    # Jupiter:
    #   13 = angular diameter
    #   23 = separation from Sun
    jupiter_query = Horizons(
        id=str(JUPITER_ID),
        location=NEXUS_LOCATION,
        epochs=epochs,
    )

    jupiter_table = jupiter_query.ephemerides(
        quantities="13,23"
    )

    if len(sun_table) != len(jupiter_table):
        raise RuntimeError(
            "Horizons returned mismatched forecast tables."
        )

    samples = []

    for sun, jupiter in zip(sun_table, jupiter_table):

        time = jd_to_datetime(sun["datetime_jd"])

        sun_elevation = float(sun["EL"])

        sun_diameter = (
            float(sun["ang_width"]) / 3600.0
        )

        jupiter_diameter = (
            float(jupiter["ang_width"]) / 3600.0
        )

        separation = float(jupiter["elong"])

        sun_radius = sun_diameter / 2.0
        jupiter_radius = jupiter_diameter / 2.0

        partial_limit = (
            jupiter_radius + sun_radius
        )

        total_limit = (
            jupiter_radius - sun_radius
        )

        # Only treat it as a visible Nexus City eclipse when
        # the Sun is geometrically above the horizon.
        visible = sun_elevation >= 0

        partial = (
            visible
            and separation <= partial_limit
        )

        total = (
            visible
            and separation <= total_limit
        )

        samples.append({
            "time": time,
            "sun_elevation": sun_elevation,
            "separation": separation,
            "partial": partial,
            "total": total,
        })

    # -------------------------------------------------------------
    # Find contiguous eclipse periods
    # -------------------------------------------------------------

    events = []
    event_start = None

    for i, sample in enumerate(samples):

        if sample["partial"] and event_start is None:
            event_start = i

        elif not sample["partial"] and event_start is not None:
            events.append(
                (event_start, i - 1)
            )
            event_start = None

    if event_start is not None:
        events.append(
            (event_start, len(samples) - 1)
        )

    # Find the first eclipse that has not already finished.
    selected = None

    for start_i, end_i in events:

        if samples[end_i]["time"] >= now:
            selected = (start_i, end_i)
            break

    if selected is None:
        return None

    start_i, end_i = selected

    event_samples = samples[
        start_i:end_i + 1
    ]

    beginning = event_samples[0]["time"]
    ending = event_samples[-1]["time"]

    maximum_sample = min(
        event_samples,
        key=lambda sample: sample["separation"],
    )

    total_samples = [
        sample
        for sample in event_samples
        if sample["total"]
    ]

    if total_samples:
        total_begin = total_samples[0]["time"]
        total_end = total_samples[-1]["time"]
    else:
        total_begin = None
        total_end = None

    return {
        "begin": beginning,
        "maximum": maximum_sample["time"],
        "end": ending,
        "total_begin": total_begin,
        "total_end": total_end,
        "minimum_separation":
            maximum_sample["separation"],
    }


# ---------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------

def format_nst(time):
    return time.strftime(
        "%A, %d %B %Y  %H:%M NST"
    )


def format_duration(start, end):
    seconds = int(
        (end - start).total_seconds()
    )

    minutes = round(seconds / 60)

    hours, minutes = divmod(
        minutes,
        60,
    )

    if hours:
        return f"{hours}h {minutes:02d}m"

    return f"{minutes}m"


# ---------------------------------------------------------------------
# Display current sky
# ---------------------------------------------------------------------

def show_current(reference_time=None):
    sky = get_sky(reference_time)

    phase = jupiter_phase(
        sky["jupiter_illumination"],
        sky["jupiter_later_illumination"],
    )

    condition = sky_condition(
        sky["sun_elevation"]
    )

    eclipse = eclipse_condition(
        sky["sun_jupiter_separation"],
        sky["sun_diameter_deg"],
        sky["jupiter_diameter_deg"],
    )

    if eclipse:
        condition = eclipse

    nst = sky["time"].strftime(
        "%A, %d %B %Y  %H:%M:%S NST"
    )

    print()
    print(
        heading("NEXUS CITY · IO")
    )
    print("0°00′N · 50°00′W")
    print("─" * 44)

    print(
        f"Nexus Standard Time    {nst}"
    )

    print()

    print(
        section_heading("IOVIAN SKY")
    )

    print(
        f"Natural condition      "
        f"{condition_style(condition)}"
    )

    print(
        f"Sun azimuth            "
        f"{sky['sun_azimuth']:6.2f}°"
    )

    print(
        f"Sun elevation          "
        f"{sky['sun_elevation']:+6.2f}°"
    )

    print()

    print(
        section_heading("JUPITER")
    )

    print(
        f"Azimuth                "
        f"{sky['jupiter_azimuth']:6.2f}°"
    )

    print(
        f"Elevation              "
        f"{sky['jupiter_elevation']:+6.2f}°"
    )

    print(
        f"Phase                  {phase}"
    )

    print(
        f"Illumination           "
        f"{sky['jupiter_illumination']:6.2f}%"
    )

    print(
        f"Apparent diameter      "
        f"{sky['jupiter_diameter_deg']:6.2f}°"
    )

    print(
        f"Phase angle            "
        f"{sky['jupiter_phase_angle']:6.2f}°"
    )

    print(
        f"Separation from Sun    "
        f"{sky['sun_jupiter_separation']:6.2f}°"
    )

    if eclipse:
        print()
        print(
            ansi(
                "⚠ JOVIAN ECLIPSE",
                "1;31",
            )
        )

        print(
            ansi(
                "Jupiter is obscuring the Sun "
                f"over {NEXUS_NAME}.",
                "1;31",
            )
        )

    print()

# ---------------------------------------------------------------------
# Display next eclipse
# ---------------------------------------------------------------------

def show_next_eclipse(reference_time=None):
    print()
    print(
        heading("NEXUS CITY · IO")
    )
    print("0°00′N · 50°00′W")
    print("─" * 44)

    print(
        section_heading(
            "NEXT JOVIAN ECLIPSE"
        )
    )

    print()

    event = find_next_eclipse(
        reference_time
    )

    if event is None:
        print(
            ansi(
                "No visible Jovian eclipse found "
                "within the next 48 hours.",
                "2",
            )
        )

        print()
        return

    print(
        ansi(
            f"Begins                 "
            f"{format_nst(event['begin'])}",
            "1;36",
        )
    )

    if event["total_begin"]:
        print(
            ansi(
                f"Totality begins        "
                f"{format_nst(event['total_begin'])}",
                "1;33",
            )
        )

    print(
        ansi(
            f"Maximum                "
            f"{format_nst(event['maximum'])}",
            "1;35",
        )
    )

    if event["total_end"]:
        print(
            ansi(
                f"Totality ends          "
                f"{format_nst(event['total_end'])}",
                "1;33",
            )
        )

    print(
        ansi(
            f"Ends                   "
            f"{format_nst(event['end'])}",
            "1;36",
        )
    )

    print(
        f"Duration               "
        f"{format_duration(event['begin'], event['end'])}"
    )

    print(
        f"Minimum separation     "
        f"{event['minimum_separation']:.3f}°"
    )

    print()

    print(
        ansi(
            "Forecast resolution: approximately 1 minute.",
            "2",
        )
    )

    print()

def show_jovian_sky(reference_time=None):
    now, bodies = get_jovian_sky(reference_time)

    nst = now.strftime(
        "%A, %d %B %Y  %H:%M:%S NST"
    )

    print()
    print(
        heading("NEXUS CITY · IO")
    )
    print("0°00′N · 50°00′W")
    print("─" * 94)

    print(
        f"Nexus Standard Time    {nst}"
    )

    print()

    print(
        section_heading("JOVIAN SYSTEM")
    )

    print()

    header = (
        f"{'Body':<12}"
        f"{'Status':<30}"
        f"{'Direction':<18}"
        f"{'Elevation':>12}"
        f"{'Size':>10}"
        f"{'From Jupiter':>14}"
    )

    print(
        ansi(header, "1")
    )

    print("─" * 96)

    for body in bodies:

        if body["name"] == "Jupiter":
            status = (
                "VISIBLE"
                if body["elevation"] >= 0
                else "BELOW HORIZON"
            )

        else:
            status = satellite_status(
                body["sat_vis"],
                body["elevation"],
            )

        size = format_apparent_size(
            body["diameter_deg"]
        )

        direction = (
            f"{compass_direction(body['azimuth'])} · "
            f"{elevation_description(body['elevation'])}"
        )

        if body["name"] == "Jupiter":
            separation = "—"

        else:
            separation = (
                f"{body['separation_deg']:.2f}°"
            )

        body_field = ansi(
            f"{body['name']:<12}",
            "1;36",
        )

        status_field = status_style(
            f"{status:<30}",
            status,
        )

        print(
            f"{body_field}"
            f"{status_field}"
            f"{direction:<18}"
            f"{body['elevation']:>+11.2f}°"
            f"{size:>10}"
            f"{separation:>14}"
        )

    print()

    print(
        section_heading("SKY SUMMARY")
    )

    print()

    for body in bodies:

        name = body["name"]

        direction = compass_direction(
            body["azimuth"]
        )

        height = elevation_description(
            body["elevation"]
        )

        if name == "Jupiter":

            if body["elevation"] >= 0:
                sentence = (
                    f"• Jupiter dominates the "
                    f"{direction} sky, {height}."
                )

                print(
                    status_style(
                        sentence,
                        "VISIBLE",
                    )
                )

            else:
                sentence = (
                    "• Jupiter is currently "
                    "below the horizon."
                )

                print(
                    status_style(
                        sentence,
                        "BELOW HORIZON",
                    )
                )

            continue

        status = satellite_status(
            body["sat_vis"],
            body["elevation"],
        )

        if status == "VISIBLE":
            sentence = (
                f"• {name} is visible {height} "
                f"in the {direction}."
            )

        elif status == "TRANSITING JUPITER":
            sentence = (
                f"• {name} is crossing "
                "the face of Jupiter."
            )

        elif status == "OCCULTED BY JUPITER":
            sentence = (
                f"• {name} is hidden behind Jupiter."
            )

        elif status == "IN JUPITER'S SHADOW":
            sentence = (
                f"• {name} is currently inside "
                "Jupiter's shadow."
            )

        elif status == "BELOW HORIZON":
            sentence = (
                f"• {name} is below "
                "the Nexus City horizon."
            )

        else:
            sentence = (
                f"• {name}: {status}."
            )

        print(
            status_style(
                sentence,
                status,
            )
        )

    print()

    print(
        ansi(
            "Angular sizes, positions, and satellite states "
            "are JPL Horizons values.",
            "2",
        )
    )

    print()

# ---------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Jovian satellite event forecasting
# ---------------------------------------------------------------------

def describe_satellite_transition(name, old_state, new_state):
    """
    Turn a Horizons state change into something readable.
    """

    if (
        old_state == "BELOW HORIZON"
        and new_state != "BELOW HORIZON"
    ):
        return f"{name} rises above the Nexus City horizon"

    if (
        old_state != "BELOW HORIZON"
        and new_state == "BELOW HORIZON"
    ):
        return f"{name} sets below the Nexus City horizon"

    transitions = {
        (
            "VISIBLE",
            "OCCULTED BY JUPITER",
        ): f"{name} disappears behind Jupiter",

        (
            "OCCULTED BY JUPITER",
            "VISIBLE",
        ): f"{name} emerges from behind Jupiter",

        (
            "VISIBLE",
            "TRANSITING JUPITER",
        ): f"{name} begins crossing Jupiter's face",

        (
            "TRANSITING JUPITER",
            "VISIBLE",
        ): f"{name} finishes crossing Jupiter's face",

        (
            "VISIBLE",
            "PARTIAL ECLIPSE",
        ): f"{name} begins entering Jupiter's shadow",

        (
            "PARTIAL ECLIPSE",
            "IN JUPITER'S SHADOW",
        ): f"{name} enters Jupiter's full shadow",

        (
            "IN JUPITER'S SHADOW",
            "PARTIAL ECLIPSE",
        ): f"{name} begins leaving Jupiter's shadow",

        (
            "PARTIAL ECLIPSE",
            "VISIBLE",
        ): f"{name} leaves Jupiter's shadow",
    }

    return transitions.get(
        (old_state, new_state),
        f"{name}: {old_state} → {new_state}",
    )


def _find_satellite_events_uncached(hours=48, reference_time=None):
    """
    Search the upcoming Jovian sky for state changes involving
    Europa, Ganymede, and Callisto.

    Sampling resolution: approximately 2 minutes.
    """

    now = (
        reference_time
        if reference_time is not None
        else datetime.now(timezone.utc)
    )

    stop = now + timedelta(hours=hours)

    epochs = {
        "start": now.strftime("%Y-%m-%d %H:%M:%S"),
        "stop": stop.strftime("%Y-%m-%d %H:%M:%S"),
        "step": "2m",
    }

    events = []

    for name, target_id in GALILEAN_MOONS.items():

        query = Horizons(
            id=str(target_id),
            location=NEXUS_LOCATION,
            epochs=epochs,
        )

        # 4  = apparent azimuth/elevation
        # 12 = satellite separation + visibility state
        table = query.ephemerides(
            quantities="4,12"
        )

        previous_state = None

        for row in table:

            event_time = jd_to_datetime(
                row["datetime_jd"]
            )

            elevation = float(row["EL"])

            state = satellite_status(
                str(row["sat_vis"]),
                elevation,
            )

            if (
                previous_state is not None
                and state != previous_state
            ):
                description = (
                    describe_satellite_transition(
                        name,
                        previous_state,
                        state,
                    )
                )

                events.append({
                    "time": event_time,
                    "body": name,
                    "description": description,
                    "old_state": previous_state,
                    "new_state": state,
                })

            previous_state = state

    events.sort(
        key=lambda event: event["time"]
    )

    return events


def find_satellite_events(hours=48, reference_time=None):
    """
    Retrieve upcoming Galilean events, using a short-lived
    local cache to avoid repeating expensive Horizons queries.
    """

    if reference_time is not None:
        return _find_satellite_events_uncached(
            hours,
            reference_time,
        )

    cache_key = (
        f"satellite-events-{hours}h"
    )

    cached = cache_load(
        cache_key,
        SATELLITE_CACHE_TTL,
    )

    if cached is not None:
        return cached

    events = (
        _find_satellite_events_uncached(
            hours
        )
    )

    cache_store(
        cache_key,
        events,
    )

    return events


def show_satellite_events(reference_time=None):
    print()
    print(
        heading("NEXUS CITY · IO")
    )
    print("0°00′N · 50°00′W")
    print("─" * 72)

    print(
        section_heading(
            "UPCOMING JOVIAN EVENTS"
        )
    )

    print()

    events = find_satellite_events(
        reference_time=reference_time
    )

    if not events:
        print(
            ansi(
                "No Galilean moon events found "
                "within the next 48 hours.",
                "2",
            )
        )

        print()
        return

    for event in events:

        timestamp = event["time"].strftime(
            "%a %d %b  %H:%M NST"
        )

        print(
            f"{ansi(f'{timestamp:<24}', '2')}"
            f"{event_style(event['description'])}"
        )

    print()

    print(
        ansi(
            "Forecast window: 48 hours · "
            "resolution: approximately 2 minutes.",
            "2",
        )
    )

    print()

# ---------------------------------------------------------------------
# Iovian daylight and twilight forecasting
# ---------------------------------------------------------------------

SOLAR_THRESHOLDS = [
    (-18.0, "astronomical"),
    (-12.0, "nautical"),
    (-6.0, "civil"),
    (0.0, "horizon"),
]


def solar_state(elevation):
    """
    Convert solar elevation into the current natural light state.
    """
    if elevation >= 0:
        return "DAY"

    if elevation >= -6:
        return "CIVIL TWILIGHT"

    if elevation >= -12:
        return "NAUTICAL TWILIGHT"

    if elevation >= -18:
        return "ASTRONOMICAL TWILIGHT"

    return "NIGHT"


def interpolate_crossing(
    time1,
    elevation1,
    time2,
    elevation2,
    threshold,
):
    """
    Estimate the time at which the Sun crossed a given
    elevation threshold between two ephemeris samples.
    """

    difference = elevation2 - elevation1

    if difference == 0:
        return time2

    fraction = (
        threshold - elevation1
    ) / difference

    return time1 + (
        time2 - time1
    ) * fraction


def describe_solar_crossing(threshold, rising):
    """
    Give a human-readable name to a twilight boundary crossing.
    """

    if rising:
        names = {
            -18.0: "Astronomical dawn begins",
            -12.0: "Nautical dawn begins",
            -6.0: "Civil dawn begins",
            0.0: "Sunrise",
        }

    else:
        names = {
            0.0: "Sunset",
            -6.0: "Civil twilight ends",
            -12.0: "Nautical twilight ends",
            -18.0: "Astronomical twilight ends",
        }

    return names[threshold]


def format_time_until(event_time, now):
    """
    Format the interval between now and an upcoming event.
    """

    seconds = max(
        0,
        int(
            (
                event_time - now
            ).total_seconds()
        ),
    )

    minutes = round(seconds / 60)

    days, minutes = divmod(
        minutes,
        24 * 60,
    )

    hours, minutes = divmod(
        minutes,
        60,
    )

    parts = []

    if days:
        parts.append(
            f"{days}d"
        )

    if hours:
        parts.append(
            f"{hours}h"
        )

    parts.append(
        f"{minutes}m"
    )

    return " ".join(parts)


def find_solar_events(hours=60, reference_time=None):
    """
    Search upcoming natural daylight and twilight transitions
    over Nexus City.

    A 60-hour window is long enough to span more than one
    complete Io solar day.
    """

    now = (
        reference_time
        if reference_time is not None
        else datetime.now(timezone.utc)
    )

    stop = now + timedelta(hours=hours)

    epochs = {
        "start": now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "stop": stop.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "step": "2m",
    }

    query = Horizons(
        id=str(SUN_ID),
        location=NEXUS_LOCATION,
        epochs=epochs,
    )

    table = query.ephemerides(
        quantities="4"
    )

    samples = []

    for row in table:
        samples.append(
            (
                jd_to_datetime(
                    row["datetime_jd"]
                ),
                float(row["EL"]),
            )
        )

    if len(samples) < 2:
        raise RuntimeError(
            "Horizons returned too few solar samples."
        )

    events = []

    previous_time, previous_el = samples[0]

    for current_time, current_el in samples[1:]:

        rising = current_el > previous_el

        for threshold, _ in SOLAR_THRESHOLDS:

            crossed_up = (
                previous_el < threshold
                <= current_el
            )

            crossed_down = (
                previous_el >= threshold
                > current_el
            )

            if not (
                crossed_up
                or crossed_down
            ):
                continue

            event_time = interpolate_crossing(
                previous_time,
                previous_el,
                current_time,
                current_el,
                threshold,
            )

            events.append({
                "time": event_time,
                "threshold": threshold,
                "rising": crossed_up,
                "description":
                    describe_solar_crossing(
                        threshold,
                        crossed_up,
                    ),
            })

        previous_time = current_time
        previous_el = current_el

    first_time, first_el = samples[0]
    second_time, second_el = samples[1]

    trend = (
        "rising"
        if second_el > first_el
        else "setting"
    )

    return (
        now,
        first_el,
        trend,
        events,
    )


def show_solar_forecast(reference_time=None):
    (
        now,
        current_el,
        trend,
        events,
    ) = find_solar_events(
        reference_time=reference_time
    )

    current_state = solar_state(
        current_el
    )

    print()
    print(
        heading("NEXUS CITY · IO")
    )
    print("0°00′N · 50°00′W")
    print("─" * 72)

    print(
        section_heading(
            "IOVIAN LIGHT CYCLE"
        )
    )

    print()

    print(
        f"{'Current':<24}"
        f"{light_state_style(current_state)}"
    )

    print(
        f"{'Sun':<24}"
        f"{current_el:+.2f}° · {trend}"
    )

    if events:
        next_event = events[0]

        print()

        print(
            section_heading(
                "NEXT TRANSITION"
            )
        )

        print()

        description_field = event_style(
            f"{next_event['description']:<30}"
        )

        print(
            f"{description_field}"
            f"{next_event['time'].strftime('%a %d %b  %H:%M NST')}"
        )

        print(
            f"{'Time until':<30}"
            f"{format_time_until(next_event['time'], now)}"
        )

    next_sunrise = next(
        (
            event
            for event in events
            if event["description"] == "Sunrise"
        ),
        None,
    )

    next_sunset = next(
        (
            event
            for event in events
            if event["description"] == "Sunset"
        ),
        None,
    )

    print()

    print(
        section_heading(
            "NEXT SUNRISE / SUNSET"
        )
    )

    print()

    if next_sunrise:

        sunrise_label = event_style(
            f"{'Sunrise':<24}"
        )

        print(
            f"{sunrise_label}"
            f"{next_sunrise['time'].strftime('%a %d %b  %H:%M NST')}"
            f"   "
            f"({format_time_until(next_sunrise['time'], now)})"
        )

    if next_sunset:

        sunset_label = event_style(
            f"{'Sunset':<24}"
        )

        print(
            f"{sunset_label}"
            f"{next_sunset['time'].strftime('%a %d %b  %H:%M NST')}"
            f"   "
            f"({format_time_until(next_sunset['time'], now)})"
        )

    print()

    print(
        section_heading(
            "UPCOMING LIGHT CHANGES"
        )
    )

    print()

    for event in events[:12]:

        timestamp = event["time"].strftime(
            "%a %d %b  %H:%M NST"
        )

        print(
            f"{ansi(f'{timestamp:<24}', '2')}"
            f"{event_style(event['description'])}"
        )

    print()

    print(
        ansi(
            "Forecast window: 60 hours · "
            "Horizons sampling: 2 minutes · "
            "crossing times interpolated.",
            "2",
        )
    )

    print()

# ---------------------------------------------------------------------
# Unified Nexus City forecast
# ---------------------------------------------------------------------

def forecast_body_description(body):
    """
    Turn the current Horizons state of a Jovian-system body
    into a short human-readable description.
    """

    direction = compass_direction(
        body["azimuth"]
    )

    height = elevation_description(
        body["elevation"]
    )

    if body["name"] == "Jupiter":

        if body["elevation"] < 0:
            return "below the horizon"

        return (
            f"{direction} · {height} · "
            f"{body['elevation']:+.1f}°"
        )

    status = satellite_status(
        body["sat_vis"],
        body["elevation"],
    )

    if status == "VISIBLE":
        return (
            f"{direction} · {height} · "
            f"{body['elevation']:+.1f}°"
        )

    if status == "BELOW HORIZON":
        return "below the horizon"

    if status == "OCCULTED BY JUPITER":
        return "hidden behind Jupiter"

    if status == "TRANSITING JUPITER":
        return "crossing Jupiter's face"

    if status == "IN JUPITER'S SHADOW":
        return "inside Jupiter's shadow"

    if status == "PARTIAL ECLIPSE":
        return "partially eclipsed by Jupiter"

    return status.lower()


def _capture_next_eclipse_report_uncached():
    """
    Reuse the existing --next eclipse forecast and return only
    its useful report lines for inclusion in --forecast.

    Color is temporarily disabled while capturing so cached
    report text never contains ANSI escape sequences.
    """
    global USE_COLOR

    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()

    previous_color = USE_COLOR

    try:
        USE_COLOR = False

        with redirect_stdout(buffer):
            show_next_eclipse()

    finally:
        USE_COLOR = previous_color

    lines = [
        line.rstrip()
        for line in buffer.getvalue().splitlines()
    ]

    marker = "NEXT JOVIAN ECLIPSE"

    if marker in lines:
        start = lines.index(marker) + 1
        lines = lines[start:]

    return [
        line
        for line in lines
        if line.strip()
    ]

def capture_next_eclipse_report():
    """
    Retrieve the next-eclipse report, caching it briefly because
    eclipse geometry does not need to be recalculated every run.
    """

    cache_key = "next-eclipse-report"

    cached = cache_load(
        cache_key,
        ECLIPSE_CACHE_TTL,
    )

    if cached is not None:
        return cached

    report = (
        _capture_next_eclipse_report_uncached()
    )

    cache_store(
        cache_key,
        report,
    )

    return report


def show_nexus_forecast():
    """
    Present the unified Nexus City astronomical forecast.
    """

    CACHE_HITS.clear()

    (
        now,
        current_sun_el,
        sun_trend,
        solar_events,
    ) = find_solar_events()

    _, bodies = get_jovian_sky()

    satellite_events = (
        find_satellite_events()
    )

    current_light = solar_state(
        current_sun_el
    )

    print()
    print("NEXUS CITY · IO")
    print("0°00′N · 50°00′W")
    print("═" * 78)

    print(
        heading(
            f"NEXUS CITY FORECAST · "
            f"iotime v{IOTIME_VERSION}"
        )
    )

    print(
        now.strftime(
            "%A, %d %B %Y  %H:%M:%S NST"
        )
    )

    print()

    # ---------------------------------------------------------
    # Current natural light
    # ---------------------------------------------------------

    print(
        section_heading("NOW")
    )
    print("─" * 78)

    print(
        f"{'Natural light':<20}"
        f"{light_state_style(current_light)}"
    )

    print(
        f"{'Sun':<20}"
        f"{current_sun_el:+.2f}° · "
        f"{sun_trend}"
    )

    if solar_events:
        next_light = solar_events[0]

        print(
            f"{'Next light change':<20}"
            f"{next_light['description']} · "
            f"{next_light['time'].strftime('%H:%M NST')} · "
            f"in "
            f"{format_time_until(next_light['time'], now)}"
        )

    print()

    # ---------------------------------------------------------
    # Current Jovian sky
    # ---------------------------------------------------------

    print(
        section_heading("JOVIAN SKY")
    )
    print("─" * 78)

    for body in bodies:
        description = (
            forecast_body_description(
                body
            )
        )

        print(
            f"{body['name']:<20}"
            f"{description}"
        )

    print()

    # ---------------------------------------------------------
    # Combined 24-hour event timeline
    # ---------------------------------------------------------

    print(
        section_heading("NEXT 24 HOURS")
    )
    print("─" * 78)

    cutoff = (
        now
        + timedelta(hours=24)
    )

    timeline = []

    for event in solar_events:
        if event["time"] <= cutoff:
            timeline.append({
                "time": event["time"],
                "description":
                    event["description"],
            })

    for event in satellite_events:
        if event["time"] <= cutoff:
            timeline.append({
                "time": event["time"],
                "description":
                    event["description"],
            })

    timeline.sort(
        key=lambda event: event["time"]
    )

    if timeline:
        for event in timeline:
            timestamp = (
                event["time"].strftime(
                    "%a %d %b  %H:%M"
                )
            )

            print(
                f"{timestamp:<23}"
                f"{event['description']}"
            )

    else:
        print(
            "No solar or Galilean moon events "
            "during the next 24 hours."
        )

    print()

    # ---------------------------------------------------------
    # Next Jovian eclipse
    # ---------------------------------------------------------

    print(
        section_heading(
            "NEXT JOVIAN ECLIPSE"
        )
    )
    print("─" * 78)

    eclipse_lines = (
        capture_next_eclipse_report()
    )

    if eclipse_lines:
        for line in eclipse_lines:
            print(line)

    else:
        print(
            "No upcoming eclipse information available."
        )

    print()

    if CACHE_HITS:
        print(
            ansi(
                "Cache: reused recent forecast data · "
                "--refresh forces new Horizons queries.",
                "2",
            )
        )

    print(
        "Natural light, Jovian positions, satellite states, "
        "and eclipse geometry use JPL Horizons data."
    )

    print()


def main():
    global USE_COLOR
    global CACHE_BYPASS

    parser = argparse.ArgumentParser(
        description=(
            "Nexus City astronomical clock "
            "and sky forecast for Io."
        )
    )

    parser.add_argument(
        "timestamp",
        nargs="?",
        help=(
            "show conditions at an NST timestamp "
            "(YYYY-MM-DDTHH:MM[:SS])"
        ),
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--next",
        action="store_true",
        help="show the next Jovian solar eclipse",
    )

    mode.add_argument(
        "--sky",
        action="store_true",
        help="show Jupiter and the Galilean moons",
    )

    mode.add_argument(
        "--events",
        action="store_true",
        help="show upcoming Galilean moon events",
    )

    mode.add_argument(
        "--sun",
        action="store_true",
        help="show upcoming daylight and twilight transitions",
    )

    mode.add_argument(
        "--forecast",
        action="store_true",
        help="show the unified Nexus City sky forecast",
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="bypass cached forecast data",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI terminal color",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=(
            f"iotime {IOTIME_VERSION}"
        ),
    )

    args = parser.parse_args()

    if args.no_color:
        USE_COLOR = False

    CACHE_BYPASS = args.refresh

    try:
        reference_time = parse_nst_timestamp(
            args.timestamp
        )

    except ValueError as error:
        parser.error(str(error))

    specialized_mode_requested = any((
        args.forecast,
    ))

    if (
        reference_time is not None
        and specialized_mode_requested
    ):
        parser.error(
            "historical timestamps currently work "
            "with the default display only; "
            "additional modes are coming in v1.1"
        )

    try:
        if args.next:
            show_next_eclipse(reference_time)

        elif args.sky:
            show_jovian_sky(reference_time)

        elif args.events:
            show_satellite_events(reference_time)

        elif args.sun:
            show_solar_forecast(reference_time)

        elif args.forecast:
            show_nexus_forecast()

        else:
            show_current(reference_time)

    except Exception as error:
        print(
            "iotime: unable to retrieve "
            "JPL Horizons data."
        )
        print()
        print(error)
        sys.exit(1)


if __name__ == "__main__":
    main()
