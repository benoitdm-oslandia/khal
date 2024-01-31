# Forecaster

## Install

Deps: `apt install vdirsyncer`

Code: `git clone github.com/benoitdm-oslandia/khal.git`, branch `feat/forecast`

## Config

### vsyndir

Create a file `~/.config/vdirsyncer/config` with this content:

```ini
[general]
# A folder where vdirsyncer can store some metadata about each pair.
status_path = "~/.config/vdirsyncer/status/"

# CALDAV
[pair my_calendar]
a = "my_calendar_local"
b = "my_calendar_remote"
collections = ["from a", "from b"]

# Calendars also have a color property
metadata = ["displayname", "color"]

[storage my_calendar_local]
type = "filesystem"
path = "~/.calendars/my_calendar_local/"
fileext = ".ics"

[storage my_calendar_remote]
type = "caldav"
url = "https://xxx.com/davical/caldav.php/"
username = "user"
password = "password"

# CALDAV
[pair ferie_calendar]
a = "ferie_calendar_local"
b = "ferie_calendar_remote"
collections = ["from a", "from b"]

# Calendars also have a color property
metadata = ["displayname", "color"]

[storage ferie_calendar_local]
type = "filesystem"
path = "~/.calendars/ferie_calendar_local/"
fileext = ".ics"

[storage ferie_calendar_remote]
type = "caldav"
url = "https://xxx.com/davical/caldav.php/"
username = "user"
password = "password"

```

Validate config: `vdirsyncer discover`

### khal

Run `khal configure` to produce `~/.config/khal/config` file with this content:

```ini
[default]
default_calendar = my_calendar

[calendars]

  [[my_calendar]]
    path = ~/.calendars/my_calendar_local/calendar/
    readonly = False

  [[ferie]]
    path = ~/.calendars/ferie_calendar_local/jours_feriers/
    readonly = True
```

### forecaster

Create a json config file `forecaster.json` like:

```json
{
    "forecasted_tasks": [
        {
            "summary": "end of trafficuk",
            "url": "2401_15_project_centre_arret_service",
            "since_date": "2024-02-26",
            "day_duration": 1,
            "repeat_per_week": 3,
            "max": 3
        },
        {
            "summary": "dev mte poc synchro",
            "url": "2311_27_mte_poc_synchro",
            "since_date": "2023-12-18",
            "day_duration": 1,
            "repeat_per_week": 4,
            "float": true,
            "max": 12
        }
    ]
}
```

## Run

1. Synchronize calendar (pull): `vdirsyncer sync`
1. Apply forecast: `bin/khal -v DEBUG forecast -a my_calendar -a ferie forecast.json`
1. Synchronize calendar again (push): `vdirsyncer sync`
