#!/usr/bin/python3
# -*- coding: utf-8 -*-

from requests.packages.urllib3.exceptions import InsecureRequestWarning
import base64
import getopt
import requests
import sys

VERSION = '1.0'


def usage():
    print(
        'Usage: %s [-P|--port=<port>] [-s|--ssl] [-w|--download-warning=<wbw>] [-c|--download-critical=<cbw>] [-W|--upload-warning=<wbw>] [-C|--upload-critical=<cbw>] [-v|--verbose] -H <host_adress> -u <username> -p <password>' %
        sys.argv[0])


def fullUsage():
    print('''check_zyxel_bandwidth v%s

Use http to check xdsl synchronized bandwidth
''' % VERSION)
    usage()
    print('''
Options:
 -h, --help
   Show this help page
 -v, --verbose
   Set verbosity to maximum
 -H, --host=HOST
   Host to test
 -P, --port=PORT
   Port used for http(s) connection
 -s, --ssl
   Use https instead of http for communication
 --no-check-certificate
   Don't check HTTPS certificate
 -u, --username=USERNAME
   Username
 -p, --password=PASSWORD
   Password
 -w, --download-warning=THRESHOLD
   If download synchronization value (in bits) is under this value, return a warning
 -c, --download-critical=THRESHOLD
   If download synchronization value (in bits) is under this value, return a critical
 -W, --upload-warning=THRESHOLD
   If upload synchronization value (in bits) is under this value, return a warning
 -C, --upload-critical=THRESHOLD
   If upload synchronization value (in bits) is under this value, return a critical
''')


def main():
    verbose = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hH:P:su:p:w:c:W:C:v',
                                   ['help', 'verbose' 'host=', 'port=', 'ssl', 'no-check-certificate', 'username=',
                                    'password=', 'download-warning=', 'download-critical=', 'upload-warning=',
                                    'upload-critical='])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(3)

    # Load paramters
    parameters = {
        'host': '',
        'port': 443,
        'ssl': False,
        'checkCertificate': True,
        'username': '',
        'password': '',
        'dwarning': 0,
        'dcritical': 0,
        'uwarning': 0,
        'ucritical': 0,
    }
    try:
        for o, a in opts:
            if o in ('-h', '--help'):
                fullUsage()
            elif o in ('-v', '--verbose'):
                verbose = True
            elif o in ('-H', '--host'):
                parameters['host'] = a
            elif o in ('-P', '--port'):
                parameters['port'] = int(a)
            elif o in ('-s', '--ssl'):
                parameters['ssl'] = True
            elif o == '--no-check-certificate':
                parameters['checkCertificate'] = False
            elif o in ('-u', '--username'):
                parameters['username'] = a
            elif o in ('-p', '--password'):
                parameters['password'] = base64.b64encode(bytes(a, "utf-8")).decode("utf-8")
            elif o in ('-w', '--download-warning'):
                parameters['dwarning'] = int(a)
            elif o in ('-c', '--download-critical'):
                parameters['dcritical'] = int(a)
            elif o in ('-W', '--upload-warning'):
                parameters['uwarning'] = int(a)
            elif o in ('-C', '--upload-critical'):
                parameters['ucritical'] = int(a)
    except ValueError:
        print('Bad parameters')
        usage()
        sys.exit(3)

    # Exit the script if mandatory parameters are not given
    if not parameters['host'] or not parameters['username'] or not parameters['password']:
        print('At least one parameter is missing')
        usage()
        sys.exit(3)

    # Define variables
    if parameters['ssl']:
        protocol = 'https'
    else:
        protocol = 'http'
    baseURL = "%s://%s:%d/" % (protocol, parameters['host'], parameters['port'])

    authObject = '{"Input_Account": "%s","Input_Passwd": "%s"}' % (parameters['username'], parameters['password'])
    httpSession = requests.Session()

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # Get authentication cookies
    requestAuthToken = httpSession.put(baseURL + "UserLoginCheck?action=check", authObject,
                                       verify=parameters['checkCertificate'])
    if requestAuthToken.status_code != 200 or requestAuthToken.json()[0]['result'] != "0":
        print("Authentication failed")
        sys.exit(3)
    httpSession.cookies.set_cookie(requests.cookies.create_cookie("Authentication", base64.b64encode(
        bytes(parameters['username'] + ":" + requestAuthToken.json()[0]['Authentication'], "utf-8")).decode("utf-8")))

    requestSessionId = httpSession.put(baseURL + "UserLoginCheck?action=add_login_entry", authObject,
                                       verify=parameters['checkCertificate'])
    if requestSessionId.status_code != 200:
        print("Authentication failed")
        sys.exit(3)

    # Get statistics
    requestStats = httpSession.get(baseURL + "cgi-bin/Status?oid=status", verify=parameters['checkCertificate'])
    for channel in requestStats.json()[0]['DslChannelInfo']:
        if channel['Status'] == 'Up':
            originalValues = [channel['DownstreamCurrRate'], channel['UpstreamCurrRate']]
    try:
        originalValues
    except NameError:
        print('UNKNOWN, No connection')
        sys.exit(3)

    # Convert bandwidth values to bit
    values = originalValues[:]
    for i, value in enumerate(values):
        values[i] = value * 1024

    # Check return value
    returnStatus = 0
    if values[0] <= parameters['dcritical']:
        returnStatus = 2
    elif values[0] <= parameters['dwarning']:
        returnStatus = 1

    if values[1] <= parameters['ucritical']:
        returnStatus = 2
    elif values[1] <= parameters['uwarning'] and returnStatus < 1:
        returnStatus = 1
    if returnStatus == 1:
        print('WARNING ', end='')
    elif returnStatus == 2:
        print('CRITICAL ', end='')
    print('Bandwidth (kbps): %d/%d | Download=%d;%d;%d;; Upload=%d;%d;%d;;' % (
        originalValues[0], originalValues[1], values[0], parameters['dwarning'], parameters['dcritical'],
        values[1],
        parameters['uwarning'], parameters['ucritical']))
    sys.exit(returnStatus)


if __name__ == '__main__':
    main()
