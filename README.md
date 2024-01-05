# Icinga 2 check plugin for UniFi Network Application

[![Pylint](https://github.com/hardoverflow/check-unifi/actions/workflows/pylint.yml/badge.svg?branch=main)](https://github.com/hardoverflow/check-unifi/actions/workflows/pylint.yml)

## Table of Contents

1. [About](#about)
2. [License](#license)
3. [Support](#support)
4. [Requirements](#requirements)
5. [Installation](#installation)
6. [Run](#run)
7. [Examples](#examples)
8. [Screenshots](#screenshots)

## About

[UniFi Network Application](https://www.ui.com/) Build powerful home and
enterprise networks with high-performance UniFi Switches, Gateways, and
Wireless Access Points. Monitor client usage, set custom traffic rules,
and much more.

This check plugin is written in Python and communicate with the REST-API of
the controller. It allows you to check the following things:

* Health state of the controller (Network Application)
* Site health state and several stats

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

```bash
usage: check_unifi.py [--help] --host HOST [--port PORT] [--ssl] [--insecure]
                      [--mode MODE] [--site-id SITE_ID] [--user USER]
                      [--password PASSWORD] [--perfdata] [--timeout TIMEOUT]
                      [--version]

Check plugin for UniFi Network Application

options:
  --help, -h            Show this help message and quit
  --host HOST, -H HOST  Host name or IP address of the UniFi Controller
  --port PORT, -p PORT  The TCP port number, (default: 8080)
  --ssl, -S             Use SSL for the connection
  --insecure, -k        Ingore ssl certificate errors (eg. self-sign cert)
  --mode MODE, -m MODE  Set the check mode: ["health", "stats"] (default:
                        health)
  --site-id SITE_ID     Site ID, (default: default)
  --user USER           Username to login
  --password PASSWORD   Password for user
  --perfdata            Enable performance data, (default: false)
  --timeout TIMEOUT     Override the plugin timeout, (default: 10)
  --version, -v         Show version number and quit
```

## Examples

### Standard health check (no authorization for this endpoint needed).

```bash
./check_unifi.py \
    --host 'controller.fqdn.com' \
    --port 443 \
    --ssl

OK: Healthy - UniFi Network Application: v8.0.24
```

### Get some site information.

```bash
./check_unifi.py \
    --host 'controller.fqdn.com' \
    --port 443 \
    --ssl \
    --mode 'stats' \
    --user 'monitoring_user' \
    --pass 'securepassword' \
    --site-id 'default'

OK: WLAN - Active APs: 4, Disconnected APs: 0, Client Devices: 19, WiFi Experience: 97.84%
```

## Screenshots

![image](https://raw.githubusercontent.com/hardoverflow/check-unifi/main/assets/images/output1.png)
![image](https://raw.githubusercontent.com/hardoverflow/check-unifi/main/assets/images/perfdata1.png)
