# iotime

**A JPL Horizons-powered astronomical clock and sky forecast for Nexus City on Io.**

`iotime` is a small command-line worldbuilding utility that answers a wonderfully specific question:

> What would the sky be doing right now if you were standing in Nexus City on Io?

Nexus City is a fictional location from the PPA setting, but its sky is driven by real astronomical data from NASA/JPL Horizons.

The canonical observing location is:

- **Io**
- **0°00′ N, 50°00′ W**
- **Nexus Standard Time (NST) = UTC**

From there, `iotime` calculates the apparent position of Sol, Jupiter, Europa, Ganymede, and Callisto, along with Jovian eclipses, moon occultations and transits, and the natural Iovian light cycle.

## Features

Running:

```bash
iotime
```

shows the current Nexus City conditions, including:

- Nexus Standard Time
- Natural daylight/twilight state
- Solar azimuth and elevation
- Jupiter azimuth and elevation
- Jupiter illumination and phase
- Jupiter apparent angular diameter
- Jovian solar-eclipse status

Additional modes provide more detailed forecasts.

## Current Jovian sky

```bash
iotime --sky
```

Shows Jupiter, Europa, Ganymede, and Callisto with human-readable directions and visibility states.

Possible satellite states include:

- visible
- below the horizon
- transiting Jupiter
- occulted by Jupiter
- partially eclipsed
- inside Jupiter's shadow

## Galilean moon events

```bash
iotime --events
```

Searches the next 48 hours for events such as:

```text
Callisto emerges from behind Jupiter
Ganymede sets below the Nexus City horizon
Europa disappears behind Jupiter
```

## Iovian daylight cycle

```bash
iotime --sun
```

Shows the current observed natural light state and upcoming solar transitions:

- astronomical twilight
- nautical twilight
- civil twilight
- sunrise
- sunset

When a Jovian eclipse is in progress, `--sun` becomes eclipse-aware. It reports the current partial or total eclipse state, shows when the next observed-light change will occur, and separately retains the next ordinary solar transition.

Because Io's natural solar day is much longer than a 24-hour human day, sunrise and sunset can occur at wonderfully strange civil times.

Nexus Standard Time remains a normal 24-hour UTC-based clock.

## Current or next Jovian eclipse

```bash
iotime --next
```

Reports the current Jovian eclipse when one is already in progress; otherwise it forecasts the next time Jupiter passes between Nexus City and Sol.

The report includes:

- eclipse beginning
- beginning of totality
- maximum eclipse
- end of totality
- eclipse end
- remaining time when an eclipse is active
- duration
- minimum angular separation

## Unified forecast

```bash
iotime --forecast
```

Combines the most useful information into one Nexus City astronomical forecast.

Example structure:

```text
NEXUS CITY FORECAST

NOW
Natural light
Solar position
Eclipse status, when active
Next solar change

JOVIAN SKY
Jupiter
Europa
Ganymede
Callisto

NEXT 24 HOURS
Solar, eclipse, and Galilean moon events

CURRENT JOVIAN ECLIPSE
or
NEXT JOVIAN ECLIPSE
Detailed eclipse report
```

During an active eclipse, the unified forecast treats the eclipse as part of the observed natural-light state, includes upcoming eclipse milestones in the 24-hour timeline, and distinguishes eclipse-driven light changes from ordinary solar transitions.

This is the recommended mode for worldbuilding and general use.

## Color output

`iotime` uses ANSI terminal color when output is connected to a compatible terminal.

Disable color manually with:

```bash
iotime --no-color
```

It also respects the standard `NO_COLOR` environment variable.

## Caching

Some Horizons queries cover many hours of ephemeris data and are relatively expensive.

`iotime` therefore caches:

- Galilean moon event forecasts
- the eclipse report used by `--forecast`

for **10 minutes**.

Current Sun and Jovian positions remain live.

Force fresh forecast data with:

```bash
iotime --forecast --refresh
```

## Installation

Clone the repository and run:

```bash
chmod +x install.sh
./install.sh
```

The installer creates:

```text
~/.local/share/iotime/
    iotime.py
    venv/

~/bin/iotime
```

No administrator privileges are required.

Make sure `~/bin` is included in your `PATH`.

## Manual installation

`iotime` requires Python plus:

```text
astropy
astroquery
```

For example:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python iotime.py --forecast
```

## Version

```bash
iotime --version
```

Current release:

```text
iotime 1.1.2
```

## Astronomy notes

The astronomical geometry comes from **NASA/JPL Horizons**, accessed through the Astropy `astroquery` package.

The observing location of Nexus City is fictional, but Horizons supports observer locations on Io and provides the real positions and apparent geometry of Solar System objects from that location.

### Twilight

Real Io has essentially no atmosphere capable of producing Earth-like twilight.

Nexus City, however, exists within an engineered breathable environment. `iotime` therefore uses the conventional solar-altitude definitions for an atmospheric sky:

- Civil twilight: Sol between 0° and -6°
- Nautical twilight: Sol between -6° and -12°
- Astronomical twilight: Sol between -12° and -18°
- Night: Sol below -18°

These twilight classifications are part of the fictional Nexus City environment; the underlying position of Sol is real Horizons geometry.

### Nexus Standard Time

Nexus Standard Time is intentionally equal to UTC.

Residents of Nexus City retain a normal 24-hour human civil clock rather than attempting to synchronize daily life with Io's approximately 42.5-hour natural light cycle.

As a result, perfectly ordinary Nexus City forecasts can contain things such as:

```text
Sunrise    19:06 NST
Sunset     16:21 NST the following day
```

That's a feature, not a bug.

## About Nexus City

Nexus City is a fictional human and extraterrestrial settlement on Io from the PPA universe.

This project began as a worldbuilding experiment: determine where on Io the city should be located so that Jupiter would dominate the sky at a dramatic but comfortable elevation.

The canonical site settled at approximately **0° N, 50° W**, where Jupiter appears roughly 40° above the horizon.

`iotime` grew from that experiment into a working astronomical forecast for the city.


## Historical sky reconstruction

Starting with **iotime 1.1.0**, any normal `iotime` mode can use a historical Nexus Standard Time timestamp instead of the current time.

Timestamp format:

```text
YYYY-MM-DDTHH:MM
```

or:

```text
YYYY-MM-DDTHH:MM:SS
```

For example:

```bash
iotime 1996-06-17T13:30
```

reconstructs the Nexus City sky at 13:30 NST on June 17, 1996.

Historical timestamps work with every display mode:

```bash
iotime 1996-06-17T13:30
iotime 1996-06-17T13:30 --sky
iotime 1996-06-17T13:30 --sun
iotime 1996-06-17T13:30 --next
iotime 1996-06-17T13:30 --events
iotime 1996-06-17T13:30 --forecast
```

The supplied timestamp becomes the reference time for the calculation.

That means historical forecasts can show:

- the natural daylight or twilight state
- the position and phase of Jupiter
- the positions and visibility states of the Galilean moons
- upcoming sunrise and sunset
- upcoming Galilean moon events
- the next Jovian solar eclipse
- a unified 24-hour Nexus City forecast

For example:

```bash
iotime 1996-06-17T13:30 --forecast
```

can reconstruct the Nexus City sky during the PPA story era and forecast astronomical events forward from that exact moment.

Historical satellite-event and eclipse forecasts bypass the normal short-lived live-data cache. This prevents cached present-day results from ever being mixed with historical calculations.

Because **Nexus Standard Time is numerically identical to UTC**, supplied timestamps are interpreted directly as NST/UTC.

## Data and trademarks

Astronomical calculations and ephemeris data are provided through NASA/JPL Horizons.

This project is not affiliated with or endorsed by NASA, JPL, Caltech, Astropy, or the developers of Astroquery.

Nexus City and the associated fictional setting are independent creative works.

## License

iotime is licensed under the BSD 3-Clause License. See [LICENSE](LICENSE) for details.
