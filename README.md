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

Shows the current natural light state and upcoming:

- astronomical twilight
- nautical twilight
- civil twilight
- sunrise
- sunset

Because Io's natural solar day is much longer than a 24-hour human day, sunrise and sunset can occur at wonderfully strange civil times.

Nexus Standard Time remains a normal 24-hour UTC-based clock.

## Next Jovian eclipse

```bash
iotime --next
```

Forecasts the next time Jupiter passes between Nexus City and Sol, including:

- eclipse beginning
- beginning of totality
- maximum eclipse
- end of totality
- eclipse end
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
Next light transition

JOVIAN SKY
Jupiter
Europa
Ganymede
Callisto

NEXT 24 HOURS
Solar and Galilean moon events

NEXT JOVIAN ECLIPSE
Detailed eclipse forecast
```

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
iotime 1.0.0
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

## Data and trademarks

Astronomical calculations and ephemeris data are provided through NASA/JPL Horizons.

This project is not affiliated with or endorsed by NASA, JPL, Caltech, Astropy, or the developers of Astroquery.

Nexus City and the associated fictional setting are independent creative works.
