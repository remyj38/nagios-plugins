#!/usr/bin/python3
# -*- coding: utf-8 -*-

import getopt
import sys
from telnetlib import Telnet

VERSION = '1.0'

def usage():
    print('Usage: %s [-P|--port=<port>] [-w|--download-warning=<wbw>] [-c|--download-critical=<cbw>] [-W|--upload-warning=<wbw>] [-C|--upload-critical=<cbw>] [-v|--verbose] -H <host_adress> -u <username> -p <password>'%sys.argv[0])

def fullUsage():
    print('''check_technicolor_bandwidth v%s

Use telnet to check xdsl synchronized bandwidth
'''%VERSION)
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
   Port used for telnet connection
 -u, --username=USERNAME
   Telnet username
 -p, --password=PASSWORD
   Telnet password
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
        opts, args = getopt.getopt(sys.argv[1:], 'hH:P:u:p:w:c:W:C:v', ['help', 'verbose' 'host=', 'port=', 'username=', 'password=', 'download-warning=', 'download-critical=', 'upload-warning=', 'upload-critical='])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(3)

    # Load paramters
    parameters = {
            'host': '',
            'port': 23,
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
            elif o in ('-u', '--username'):
                parameters['username'] = a
            elif o in ('-p', '--password'):
                parameters['password'] = a
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
    
    # Telnet connection to retrieve bandwidth
    connection = Telnet(parameters['host'], parameters['port'])
    if verbose:
        connection.set_debuglevel(9)
    connection.read_until(b'Username : ')
    connection.write(parameters['username'].encode('ascii') + b'\r')
    connection.read_until(b'Password : ')
    connection.write(parameters['password'].encode('ascii') + b'\r')
    if 'Closing connection' in connection.read_until(b'{%s}=>'%parameters['username'].encode('ascii'), 7).decode('ascii'):
        print('Invalid username or password')
        sys.exit(2)
    connection.write(b'xdsl info\r')
    connection.write(b'exit\r')
    data = connection.read_all().decode('ascii')
    connection.close()
    del connection

    # Extract bandwidth data from connection data
    originalValues = []
    unit = ''
    for line in data.splitlines():
        if 'Bandwidth' in line:
            line = line.split('\t\t')
            originalValues = [int(x) for x in line[-1][1:].split('/')]
            unit = line[0][-9:-5].lower()
            break
    if not originalValues or not unit:
        print('No values returned')
        sys.exit(2)

    # Convert bandwidth values to bit
    values = originalValues[:]
    for i, value in enumerate(values):
        if unit == 'gbit':
            values[i] = value*1024**3
        if unit == 'mbit':
            values[i] = value*1024**2
        if unit == 'kbit':
            values[i] = value*1024

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
    print('Bandwidth (%s): %d/%d | Download=%d;%d;%d;; Upload=%d;%d;%d;;'%(unit, originalValues[0], originalValues[1], values[0], parameters['dwarning'], parameters['dcritical'], values[1], parameters['uwarning'], parameters['ucritical']))
    sys.exit(returnStatus)

if __name__ == '__main__':
    main()
