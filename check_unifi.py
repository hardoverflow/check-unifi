#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Check plugin for UniFi Network Application
"""

from statistics import mean
import argparse
import os
import re
import sys
import requests

__version__ = '0.1'


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
                        help='Show this help message and exit')

    # Host name or IP address
    parser.add_argument('--host', '-H', type=str, required=True,
                        default=os.environ.get('CHECK_UNIFI_HOST'),
                        help='Host name or IP address of the UniFi Controller')

    # Port number
    parser.add_argument('--port', '-p', type=int, required=False,
                        default=os.environ.get('CHECK_UNIFI_PORT', 443),
                        help='The TCP port number, (default: 443)')

    # Enable SSL for the connection
    parser.add_argument('--ssl', '-S', action='store_true', required=False,
                        help='Use SSL for the connection')

    # Mode of the check plugin
    parser.add_argument('--mode', '-m', type=str, required=False,
                        default=os.environ.get('CHECK_UNIFI_MODE', 'health'),
                        help='Mode of the check, (default: health)')

    # Site ID
    parser.add_argument('--site-id', type=str, required=False,
                        default=os.environ.get('CHECK_UNIFI_SITE_ID',
                                               'default'),
                        help='Site ID, (default: default)')

    # Username
    parser.add_argument('--user', type=str, required=False,
                        default=os.environ.get('CHECK_UNIFI_USER'),
                        help='Username')

    # Password
    parser.add_argument('--password', type=str, required=False,
                        default=os.environ.get('CHECK_UNIFI_PASS'),
                        help='Password for user')

    # Enable performance data
    parser.add_argument('--perfdata', action='store_true', required=False,
                        help='Enable performance data, (Default: false)')

    # Timeout
    parser.add_argument('--timeout', type=int, required=False,
                        default=10,
                        help='Override the plugin timeout, (default: 10)')

    # Version
    parser.add_argument('--version', '-v', action='version',
                        version=f'%(prog)s {__version__}',
                        help='Show the version number and exit')

    # Return arguments
    return parser.parse_args()


def check_health(args):
    """
    Get the health state of the controller

    """
    state, msg, perf = 3, None, None
    proto = 'https' if args.ssl else 'http'
    uri = f'{proto}://{args.host}/status'

    try:
        resp = requests.get(uri, allow_redirects=False, timeout=5)
        if re.match(r'^30\d', str(resp.status_code)):
            return {'state': 3, 'message': f'Found redirection for {uri}. '
                    'Wrong protocol?', 'perfdata': None}
    except requests.exceptions.ConnectionError:
        return {'state': 3, 'message': 'There was a connection problem for: '
                f'{uri}', 'perfdata': None}

    if resp.json()['meta']['up'] and resp.json()['meta']['rc'] == 'ok':
        state = 0
        msg = 'Healthy - UniFi Network Application: v' + \
              f'{resp.json()["meta"]["server_version"]}'

    return {"state": state, "message": msg, "perfdata": perf}


def api_login(args):
    """
    Performs API login

    """
    header = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    payload = {'username': args.user, 'password': args.password}
    proto = 'https' if args.ssl else 'http'
    uri = f'{proto}://{args.host}/api/login'

    req = requests.Session()

    try:
        req.post(uri, headers=header, json=payload, allow_redirects=False,
                 timeout=5)
    except requests.exceptions.ConnectionError:
        print(f'There was a connection problem for: {uri}')
        sys.exit(3)

    return req


def check_site_stats(args):
    """
    Get site health state by site id

    """
    # Define some variables
    header = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    state, msg, perf = 3, None, {}
    proto = 'https' if args.ssl else 'http'
    uri_0 = f'{proto}://{args.host}/api/s/{args.site_id}/stat/health'
    uri_1 = f'{proto}://{args.host}/api/s/{args.site_id}/stat/sta'

    # Require a valid session to query the api endpoint
    req = api_login(args)

    # Get site stats
    try:
        resp_0 = req.get(uri_0, headers=header, allow_redirects=False,
                         timeout=5)
    except requests.exceptions.ConnectionError:
        return {'state': 3, 'message': 'There was a connection problem for: '
                f'{uri_0}', 'perfdata': None}

    # List of all active clients on site
    try:
        resp_1 = req.get(uri_1, headers=header, allow_redirects=False,
                         timeout=5)
    except requests.exceptions.ConnectionError:
        return {'state': 3, 'message': 'There was a connection problem for: '
                f'{uri_1}', 'perfdata': None}

    stats_site = resp_0.json()
    stats_wifi_exp = mean([item for item in
                           [item.get('satisfaction')
                            for item in resp_1.json()['data']]
                          if item is not None])

    state = 0 if stats_site['data'][0]['status'] == 'ok' else 1

    msg = f'WLAN - Active APs: {stats_site["data"][0]["num_ap"]}, ' + \
          f'Disconnected APs: {stats_site["data"][0]["num_disconnected"]},' + \
          f' Client Devices: {stats_site["data"][0]["num_user"]}, ' + \
          f'WiFi Experience: {stats_wifi_exp:.2f}%'

    if args.perfdata:
        # Take over all stats
        perf = stats_site['data'][0]

        # Add additional keys
        perf.update({'wifi_experience': f'{stats_wifi_exp:.2f}%'})

        # Remove some useless keys
        for key in ('status', 'subsystem'):
            perf.pop(key, None)

        # Append Unit of Measurement (UoM)
        for key in ('rx_bytes-r', 'tx_bytes-r'):
            perf.update({key: str(stats_site['data'][0][key]) + 'B'})

    return {'state': state, 'message': msg, 'perfdata': perf}


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
    Main function
    """

    # Parse arguments
    args = args_parse()

    if args.mode == 'health':
        fmt_output(check_health(args))
    if args.mode == 'stats':
        fmt_output(check_site_stats(args))


if __name__ == '__main__':
    main()
