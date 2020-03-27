#!/bin/bash

describe_openssl_error () {
    grep -i 'no peer certificate available' $tmp_folder/openssl.out &>/dev/null
    if [ $? -eq 0 ]; then
        echo "No certificate sent by server"
    else
        # Source: https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/errno.h
        case "$(awk -F'=' '/connect:errno/{print $2}' $tmp_folder/openssl.err)" in
            "11" | "110")
                echo "Timeout"
                ;;
            "22")
                echo "Name or service not known"
                ;;
            "71")
                echo "Protocol error"
                ;;
            "92")
                echo "Protocol not available"
                ;;
            "93")
                echo "Protocol not supported"
                ;;
            "111")
                echo "Connection refused"
                ;;
            "112")
                echo "Host is down"
                ;;
            "113")
                echo "No route to host"
                ;;
            *)
                echo "Unknown error"
                cat $tmp_folder/openssl.err
                ;;
        esac
    fi
}

return_message() {
    case "$1" in
        0)
            echo "OK: $2"
            ;;
        1)
            echo "WARNING: $2"
            ;;
        2)
            echo "CRITICAL: $2"
            ;;
        3)
            echo "UNKNOWN: $2"
            ;;
    esac
    rm -rf $tmp_folder
    exit $1
}

usage () {
    cat << EOF
Usage: $0 -H hostname -p port -s type

Check certificate expiration date

Options:
 -h
      Print this help
 -c days
      Minimum number of days before critical alert (default=30)
 -H hostname
      Host name or IP Address
 -p port
      Port number
 -s protocol
      Send the protocol-specific message(s) to switch to TLS for communication.
      Allowed values:
        - smtp
        - pop3
        - imap
        - ftp
        - xmpp
        - xmpp-server
        - irc
        - postgres
        - mysql
        - lmtp
        - nntp
        - sieve
        - ldap
 -v
      Verify certificate hostname match
 -w days
      Minimum number of days before warning alert (default=60)
EOF
    exit 3
}

test_missing_arg () {
    if [[ $OPTARG == -* ]]; then
        echo "Argument required for -$option"
        usage
    fi
}

is_int='^[0-9]+$'
while getopts ":c:hH:p:s:vw:" option;do
    case $option in
        c)
            test_missing_arg
            if ! [[ $OPTARG =~ $is_int ]] ; then
                echo "-c should be an integer"
                usage
            fi
            critical=$(( $OPTARG ))
            ;;
        h)
            usage
            ;;
        H)
            test_missing_arg
            host="$OPTARG"
            ;;
        p)
            test_missing_arg
            port="$OPTARG"
            ;;
        s)
            test_missing_arg
            starttls="$OPTARG"
            ;;
        v)
            verify="true"
            ;;
        w)
            test_missing_arg
            if ! [[ $OPTARG =~ $is_int ]] ; then
                echo "-w should be an integer"
                usage
            fi
            warning=$(( $OPTARG ))
            ;;
        :)
            echo "Argument required for -$OPTARG"
            usage
            ;;
        \?)
            echo "$OPTARG : unknown option"
            usage
            ;;
    esac
done

[[ -z "$host" ]] && echo "-H hostname is mandatory" && usage
[[ -z "$port" ]] && echo "-p port is mandatory" && usage
[[ -z "$critical" ]] && critical=30
[[ -z "$warning" ]] && warning=60
[[ -n "$verify" ]] && options="-verify_hostname $host"
[[ -n "$starttls" ]] && options="${options} -starttls ftp"

tmp_folder=$(mktemp -d)

echo "QUIT" | openssl s_client -host $host -port $port ${options} 2>$tmp_folder/openssl.err 1>$tmp_folder/openssl.out
if [ $? -ne 0 ]; then
    return_message 3 "Unable to get certificate : $(describe_openssl_error)"
fi

# Certificate verification: expiry and hostname
verification_status=$(awk -F': ' '/Verification error: /{ print $2}' $tmp_folder/openssl.out)
if [ -n "$verification_status" ]; then
    return_message 2 "Error on certificate validation: $verification_status"
fi

expiry_date=$(openssl x509 -in $tmp_folder/openssl.out -noout -text | awk -F':' '/Not After/{print $2}')
critical_delta=$(( ( $(date -d "$expiry_date -${critical} days" +%s) - $(date +%s) ) / (60*60*24) ))
warning_delta=$(( ( $(date -d "$expiry_date -${warning} days" +%s) - $(date +%s) ) / (60*60*24) ))

if [ $critical_delta -le 0 ]; then
    return_code=2
elif [ $warning_delta -le 0 ]; then
    return_code=1
else
    return_code=0
fi

return_message $return_code "Certificate '$(openssl x509 -in $tmp_folder/openssl.out -noout -text | awk -F'=' '/Subject:.*, CN ?= ?/{print $NF}')' will expire on $(date -d "$expiry_date")"
