#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Author:  Daniel Schade, Fabian Ihle
# Contact: mail (at) bashlover (de)
# License: The Unlicense, see UNLICENSE file.

"""
Check plugin for UniFi Network Application
"""

from functools import partial
from statistics import mean
import argparse
import os
import re
import signal
import sys
import requests
from urllib3.exceptions import InsecureRequestWarning

__version__ = '0.6'


def handle_sigalrm(signum, frame, timeout=None): # pylint: disable=W0613
    """
    Handle a timeout
    """
    print(f'UNKNOWN: Plugin timed out after {timeout} seconds')
    sys.exit(3)


def args_parse():
    """
    This function parses arguments, ensures that required parameters have
    argumnets, offfers help as well as version information and return the
    argparse arguments namespace
    """

    # Setup argument parser
    parser = argparse.ArgumentParser(
            add_help=False,
            prog='check_unifi.py',
            description='Check plugin for UniFi Network Application'
    )

    parser.add_argument('--help', '-h', action='help',
                        default=argparse.SUPPRESS,
                        help='Show this help message and quit')

    # Host name or IP address of the controller
    parser.add_argument('--host', '-H', type=str, required=True,
                        default=os.environ.get('CHECK_UNIFI_HOST'),
                        help='Host name or IP address of the UniFi Controller')

    # Set the port number where the controller is listening
    parser.add_argument('--port', '-p', type=int, required=False,
                        default=os.environ.get('CHECK_UNIFI_PORT', 8080),
                        help='The TCP port number, (default: 8080)')

    # Enable ssl for the connection
    parser.add_argument('--ssl', '-S', action='store_true', required=False,
                        help='Use SSL for the connection')

    # Disable certificate check if eg. self-signed
    parser.add_argument('--insecure', '-k', action='store_false',
                        required=False, help='Ingore ssl certificate errors \
                                (eg. self-sign cert)')

    # Set the mode of the check
    parser.add_argument('--mode', '-m', type=str, required=False,
                        default=os.environ.get('CHECK_UNIFI_MODE', 'health'),
                        help='Set the check mode: ["health", "stats", \
                                "devices", "firmware", "version", "all"] \
                                (default: health)')

    # Set the site-id
    parser.add_argument('--site-id', type=str, required=False,
                        default=os.environ.get('CHECK_UNIFI_SITE_ID',
                                               'default'),
                        help='Site ID, (default: default)')

    # Toggle between the legacy standalone Network Application endpoints and
    # the UniFi OS / UniFi OS Server endpoints (e.g. UDM, Cloud Key Gen2,
    # self-hosted UniFi OS Server). UniFi OS prefixes the Network API with
    # /proxy/network and uses /api/auth/login for authentication.
    parser.add_argument('--unifi-os', action='store_true', required=False,
                        default=os.environ.get('CHECK_UNIFI_OS', '').lower()
                        in ('1', 'true', 'yes'),
                        help='Use UniFi OS / UniFi OS Server endpoints \
                                (/proxy/network ...). Omit for a legacy \
                                standalone Network Application, (default: false)')

    # Set the username to login
    parser.add_argument('--user', type=str, required=False,
                        default=os.environ.get('CHECK_UNIFI_USER'),
                        help='Username to login')

    # Set the password of the user
    parser.add_argument('--password', type=str, required=False,
                        default=os.environ.get('CHECK_UNIFI_PASS'),
                        help='Password for user')

    # Enable performance data
    parser.add_argument('--perfdata', action='store_true', required=False,
                        help='Enable performance data, (default: false)')

    # Set the timeout of the check
    parser.add_argument('--timeout', type=int, required=False,
                        default=10,
                        help='Override the plugin timeout, (default: 10)')

    # Show the version of the check plugin
    parser.add_argument('--version', '-v', action='version',
                        version=f'%(prog)s {__version__}',
                        help='Show version number and quit')

    # Return arguments
    return parser.parse_args()


def build_urls(args):
    """
    Build the API endpoint URLs for the legacy standalone Network Application
    or, with --unifi-os, the UniFi OS proxy (/proxy/network, /api/auth/login).
    """
    scheme = 'https' if args.ssl else 'http'
    base = f'{scheme}://{args.host}:{args.port}'

    if args.unifi_os:
        return {
            'login': f'{base}/api/auth/login',
            'logout': f'{base}/api/auth/logout',
            'status': f'{base}/proxy/network/status',
            'site': f'{base}/proxy/network/api/s/{args.site_id}',
        }

    return {
        'login': f'{base}/api/login',
        'logout': f'{base}/api/logout',
        'status': f'{base}/status',
        'site': f'{base}/api/s/{args.site_id}',
    }


def check_health(args, req=None):
    """
    Get the health state of the controller

    """
    state, msg, perf = 3, None, None
    uri = build_urls(args)['status']

    if not args.insecure:
        requests.packages.urllib3.disable_warnings( # pylint: disable=E1101
                category=InsecureRequestWarning)

    # The legacy /status endpoint is public; UniFi OS requires a session.
    if req is not None:
        requester = req
    elif args.unifi_os:
        requester = api_login(args)
    else:
        requester = requests

    try:
        resp = requester.get(uri, allow_redirects=False, timeout=5,
                             verify=bool(args.insecure))

        # Redirection messages (300-399)
        if re.match(r'^3\d\d', str(resp.status_code)):
            return {'state': 3, 'message': f'Found redirection for {uri}. '
                    'Wrong protocol?', 'perfdata': None}

        # Server error responses (500-599)
        if re.match(r'^5\d\d', str(resp.status_code)):
            return {'state': 2, 'message': f'Connection to {uri} failed. '
                    f'Status Code: {resp.status_code}', 'perfdata': None}

        # Unauthorized - usually the wrong path/port for the deployment type
        if resp.status_code == 401:
            return {'state': 3, 'message': f'Unauthorized for {uri}. '
                    'Wrong endpoint type? Try toggling --unifi-os.',
                    'perfdata': None}

    # Exception for a connection error
    except requests.exceptions.ConnectionError:
        return {'state': 2, 'message': f'Connection to {uri} failed. ',
                'perfdata': None}

    # JSON to dict
    try:
        blob = resp.json()
    except ValueError:
        return {'state': 3, 'message': f'Non-JSON response from {uri} '
                f'(HTTP {resp.status_code}). Wrong endpoint type or port? '
                'Try toggling --unifi-os.', 'perfdata': None}

    # A body without "meta" means we hit the wrong status endpoint
    if not isinstance(blob, dict) or 'meta' not in blob:
        return {'state': 3, 'message': f'Unexpected status payload from {uri}. '
                'Wrong endpoint type? Try toggling --unifi-os. '
                f'Response: {str(blob)[:200]}', 'perfdata': None}

    # Healthy when rc is 'ok'; legacy also exposes 'up', UniFi OS does not
    meta = blob['meta']
    if meta.get('rc') == 'ok' and meta.get('up', True):
        version = meta.get('server_version')
        msg = 'Healthy - UniFi Network Application' + \
              (f': v{version}' if version else '')
        state = 0
    else:
        msg, state = 'Unhealthy', 1

    # Returns the state and message only
    return {"state": state, "message": msg, "perfdata": perf}


def api_login(args):
    """
    Performs API login

    """
    header = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    payload = {'username': args.user, 'password': args.password}
    uri = build_urls(args)['login']

    # Create a session object
    req = requests.Session()
    req.headers.update(header)

    # Disable ssl certificate check
    if not args.insecure:
        requests.packages.urllib3.disable_warnings( # pylint: disable=E1101
                category=InsecureRequestWarning)
        req.verify = False

    try:
        # Login with given credentials
        resp = req.post(uri, headers=header, json=payload,
                        allow_redirects=False, timeout=5)

    # Exception for a connection error
    except requests.exceptions.ConnectionError:
        print(f'UNKNOWN: There was a connection problem for: {uri}')
        sys.exit(3)

    # Reject invalid credentials early
    if resp.status_code in (400, 401):
        print(f'UNKNOWN: Login failed for {uri}. Check username/password.')
        sys.exit(3)

    # Return the session object
    return req


def check_site_stats(args, req=None):
    """
    Get site health state by site id

    """
    # Define some variables
    header = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    blob, state, msg, perf = [], 3, None, {}
    site = build_urls(args)['site']
    uri = [f'{site}/stat/health',
           f'{site}/stat/sta']

    # Require a valid session to query the api endpoint
    req = req or api_login(args)

    for url in uri:
        try:
            # Collect data from endpoint
            resp = req.get(url, headers=header, allow_redirects=False,
                             timeout=5)

        # Exception for a connection error
        except requests.exceptions.ConnectionError:
            return {'state': 3, 'message': 'There was a connection problem '
                    f'for: {url}', 'perfdata': None}

        # Detects a redirection
        if re.match(r'^30\d', str(resp.status_code)):
            return {'state': 3, 'message': f'Found redirection for {uri}. '
                    'Wrong protocol?', 'perfdata': None}

        # Unauthorized
        if resp.status_code == 401:
            return {'state': 3, 'message': 'Unauthorized. Login is required.',
                    'perfdata': None}

        blob.append(resp.json())

    # Calculate WiFi Experience
    try:
        stats_wifi_exp = mean([item for item in
                               [item.get('satisfaction')
                                for item in blob[1]['data']]
                              if item is not None])
    except: # pylint: disable=W0702
        # If no client connected, set stats_wifi_exp to 100%
        stats_wifi_exp = 100

    # Health state of the site
    state = 0 if blob[0]['data'][0]['status'] == 'ok' else 1

    # Format the output
    msg = f'WLAN - Active APs: {blob[0]["data"][0]["num_ap"]}, ' + \
          f'Disconnected APs: {blob[0]["data"][0]["num_disconnected"]},' + \
          f' Client Devices: {blob[0]["data"][0]["num_user"]}, ' + \
          f'WiFi Experience: {stats_wifi_exp:.2f}%'

    if args.perfdata:
        # Take over all stats
        perf = blob[0]['data'][0]

        # Add additional keys
        perf.update({'wifi_experience': f'{stats_wifi_exp:.2f}%'})

        # Remove some useless keys
        for key in ('status', 'subsystem'):
            perf.pop(key, None)

        # Append Unit of Measurement (UoM)
        for key in ('rx_bytes-r', 'tx_bytes-r'):
            perf.update({key: str(blob[0]['data'][0][key]) + 'B'})

    return {'state': state, 'message': msg, 'perfdata': perf}


def api_fetch(req, url):
    """
    Authenticated GET against an API endpoint. Returns (data, error): on
    success the JSON "data" list and None, otherwise None and a result struct.
    """
    try:
        resp = req.get(url, allow_redirects=False, timeout=5)

    # Exception for a connection error
    except requests.exceptions.ConnectionError:
        return None, {'state': 3, 'message': 'There was a connection problem '
                      f'for: {url}', 'perfdata': None}

    # Detects a redirection
    if re.match(r'^30\d', str(resp.status_code)):
        return None, {'state': 3, 'message': f'Found redirection for {url}. '
                      'Wrong protocol?', 'perfdata': None}

    # Unauthorized
    if resp.status_code == 401:
        return None, {'state': 3, 'message': 'Unauthorized. Login is required.',
                      'perfdata': None}

    try:
        blob = resp.json()
    except ValueError:
        return None, {'state': 3, 'message': f'Non-JSON response from {url} '
                      f'(HTTP {resp.status_code}).', 'perfdata': None}

    return blob.get('data', []), None


def check_devices(args, req=None):
    """
    Check adopted devices (APs, switches, gateways) for connectivity
    """
    req = req or api_login(args)
    data, error = api_fetch(req, f'{build_urls(args)["site"]}/stat/device')
    if error:
        return error

    # state == 1 means connected; anything else is a problem
    offline = [d.get('name') or d.get('mac') for d in data
               if d.get('state') != 1]
    total, down = len(data), len(offline)

    state = 2 if down else 0
    msg = f'Devices - Total: {total}, Connected: {total - down}, ' + \
          f'Disconnected: {down}'
    if offline:
        msg += f' [{", ".join(offline)}]'

    perf = None
    if args.perfdata:
        perf = {'devices_total': total,
                'devices_connected': total - down,
                'devices_disconnected': down}

    return {'state': state, 'message': msg, 'perfdata': perf}


def check_firmware(args, req=None):
    """
    Check for adopted devices with a pending firmware upgrade
    """
    req = req or api_login(args)
    data, error = api_fetch(req, f'{build_urls(args)["site"]}/stat/device')
    if error:
        return error

    upgradable = [d.get('name') or d.get('mac') for d in data
                  if d.get('upgradable')]

    state = 1 if upgradable else 0
    if upgradable:
        msg = f'Firmware - Updates available: {len(upgradable)} ' + \
              f'[{", ".join(upgradable)}]'
    else:
        msg = 'Firmware - All devices up to date'

    perf = {'devices_upgradable': len(upgradable)} if args.perfdata else None

    return {'state': state, 'message': msg, 'perfdata': perf}


def check_version(args, req=None):
    """
    Report the UniFi Network Application version (informational)
    """
    req = req or api_login(args)
    data, error = api_fetch(req, f'{build_urls(args)["site"]}/stat/sysinfo')
    if error:
        return error

    if not data:
        return {'state': 3, 'message': 'No sysinfo data returned',
                'perfdata': None}

    version = data[0].get('version', 'unknown')
    return {'state': 0,
            'message': f'UniFi Network Application: v{version}',
            'perfdata': None}


def check_all(args, checks):
    """
    Run every check, returning the worst state and merged perfdata.
    """
    # Log in once and reuse the session across all sub-checks
    req = api_login(args)

    state, parts, perf = 0, [], {}
    for name, func in checks.items():
        result = func(args, req)
        state = max(state, result['state'])
        parts.append(f'[{name}] {result["message"]}')
        if result.get('perfdata'):
            perf.update(result['perfdata'])

    return {'state': state, 'message': ' | '.join(parts),
            'perfdata': perf or None}


def fmt_output(struct):
    """
    Format the output and exit the program with return code
    """
    # Define the monitoring states
    states = ['OK', 'WARNING', 'CRITICAL', 'UNKNOWN']

    # Format and print output
    if struct['perfdata']:
        # Concat perfdata
        print(f'{states[struct["state"]]}: {struct["message"]} | ' +
              ' '.join([f'\'{key}\'={val}'
                       for key, val in sorted(struct['perfdata'].items())]))
    else:
        print(f'{states[struct["state"]]}: {struct["message"]}')

    sys.exit(struct['state'])


def main():
    """
    Icinga 2 check for UniFi Network Application
    """
    # Parse arguments
    args = args_parse()

    # Handle timeout
    signal.signal(signal.SIGALRM, partial(handle_sigalrm, timeout=args.timeout))
    signal.alarm(args.timeout)

    # Map the check modes to their implementation
    checks = {
        'health': check_health,
        'version': check_version,
        'devices': check_devices,
        'firmware': check_firmware,
        'stats': check_site_stats,
    }

    if args.mode == 'all':
        fmt_output(check_all(args, checks))
    elif args.mode in checks:
        fmt_output(checks[args.mode](args))
    else:
        print(f'UNKNOWN: Unknown mode "{args.mode}". Valid modes: ' +
              ', '.join(list(checks) + ['all']))
        sys.exit(3)


if __name__ == '__main__':
    main()
