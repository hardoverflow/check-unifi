# Icinga 2 check plugin for UniFi Network Application

#### Table of Contents

1. [About](#about)
2. [License](#license)
3. [Support](#support)
4. [Requirements](#requirements)
5. [Installation](#installation)
6. [Run](#run)
7. [Examples](#examples)

## About

[UniFi Network Application](https://www.ui.com/) Build powerful home and
enterprise networks with high-performance UniFi Switches, Gateways, and
Wireless Access Points. Monitor client usage, set custom traffic rules,
and much more.

This check plugin allows you to check:

* Health state of the controller (Network Application)
* Site health and stats

Additional features:

* Performance data

## License

Lincensed under the [UNLICENSE](https://unlicense.org/), which is a license
with no conditions whatsoever that dedicates works to the public domain.

## Support

For bugs and feature requests please head over to the
[issue tracker](https://github.com/hardoverflow/check-unifi/issues).

## Requirements

* Python 3.x
* `requests` Python library

## Installation

```bash
pip install requests
```

## Run

```
usage: check_unifi.py [--help] --host HOST [--port PORT] [--ssl] [--mode MODE] [--site-id SITE_ID] [--user USER] [--password PASSWORD] [--perfdata] [--timeout TIMEOUT] [--version]

Check plugin for UniFi Network Application

options:
  --help, -h            Show this help message and exit
  --host HOST, -H HOST  Host name or IP address of the UniFi Controller
  --port PORT, -p PORT  The TCP port number, (default: 443)
  --ssl, -S             Use SSL for the connection
  --mode MODE, -m MODE  Mode of the check, (default: health)
  --site-id SITE_ID     Site ID, (default: default)
  --user USER           Username
  --password PASSWORD   Password for user
  --perfdata            Enable performance data, (Default: false)
  --timeout TIMEOUT     Override the plugin timeout, (default: 10)
  --version, -v         Show the version number and exit
```

## Examples

Standard health check (no authorization for this endpoint needed)
```
# Example: ./check_unifi.py -H controller.fqdn.com --ssl
OK: Healthy - UniFi Network Application: v7.3.76
```
