#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Check plugin for Unifi Controller
"""

import argparse
import os
import sys
import requests

__version__ = '1.0'


def args_parse():
    """
    This function parses arguments, ensures that required parameters have
    argumnets, offfers help as well as version information and return the
    argparse arguments namespace
    """

    # Setup argument parser
    parser = argparse.ArgumentParser(
            prog='check_unifi.py',
            description='Check plugin for Unifi Controller'
    )

    # Host name or IP address
    parser.add_argument('--host', '-H', type=str, required=True,
                        default=os.environ.get('CHECK_UNIFI_HOST'),
                        help='Host name or IP address of the Unifi Controller')

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

    # Timeout
    parser.add_argument('--timeout', type=int, required=False,
                        default=10,
                        help='Override the plugin timeout, (default: 10)')

    # Version
    parser.add_argument('--version', '-v', action='version',
                        version=f'%(prog)s {__version__}',
                        help='Show the version number and exit')

    # Return arguments
    # print(parser.parse_args())
    return parser.parse_args()


def check_health(args):
    """
    Get the health state of the controller

    """
    state, msg, perfdata = 3, None, None
    proto = 'https' if args.ssl else 'http'
    uri = f'{proto}://{args.host}/status'

    try:
        req = requests.get(uri, allow_redirects=False, timeout=5)
        if req.json()['meta']['up'] and req.json()['meta']['rc'] == 'ok':
            state = 0
            msg = 'Healthy - Unifi Network Application Version: ' + \
                  f'{req.json()["meta"]["server_version"]}'
    except Exception:
        state = 2
        msg = 'Unhealthy - Cannot get controller health state'

    return {"state": state, "message": msg, "perfdata": perfdata}


def output(struct):
    """
    Format the output and exit the program with return code
    """
    # Define the monitoring states
    states = ['OK', 'WARNING', 'CRITICAL', 'UNKNOWN']

    print(f'{states[struct["state"]]}: {struct["message"]}')
    sys.exit(struct["state"])


def main():
    """
    Main function
    """

    # Parse arguments
    args = args_parse()

    if args.mode == 'health':
        output(check_health(args))


if __name__ == '__main__':
    main()
