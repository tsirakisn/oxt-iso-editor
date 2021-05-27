#!/bin/bash

# check .py files for errors

lint() {
    files="$1"
    errors_only="$2"

    if [ -z "$files" ]; then
        echo "nothing to do."
        exit 0
    fi

    # W0511: TODO/FIXME/etc
    # W0702: bare exception
    # W0703: too general exception
    # C0103: single letter variable names
    # C0114-116: missing docstrings
    # C0301: line too long
    # C0411: wrong import order
    # R0201: no self use in method
    # R0902: too many instance attributes
    # R0903: too few instance attributes
    # R0912: too many function arguments
    disable_arg="E0611,E0401,W0511,W0702,W0703,C0103,C0114,C0115,C0116,C0301,C0411,R0201,R0902,R0903,R0913"

    if [ "$errors_only" == "yes" ]; then
        disable_arg="C,R,W,$disable_arg"
    fi

    echo "$files" | xargs pylint -d $disable_arg
}

if [[ $(which pylint) == "" ]]; then
    echo "pylint not installed. install with pip3."
    exit
fi

errors_only="no"
files=""

while [[ $# -gt 0 ]]; do
    arg="$1"
    case "$arg" in
        -e|--errors-only)
            errors_only="yes"
            shift
            ;;
        -f|--file)
            files="$2 $files"
            shift 2
            ;;
        *)
            echo "usage: $0 [-f|--file FILE] [-e|--errors-only]"
            echo "file arg can be specified as many times as needed"
            exit
            ;;
    esac
done

# user didn't specify any files, use all
if [ -z "$files" ]; then
    files="$(find . -name '*.py')"
fi

lint "$files" "$errors_only"
