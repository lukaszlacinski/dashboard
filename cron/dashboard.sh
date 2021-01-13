#!/bin/bash

cd "$(dirname "$0")"
if [ ! -d log ]; then
    mkdir log
fi
/opt/dashboard/venv/bin/python dashboard.py -c endpoints_aps.json -s aps
/opt/dashboard/venv/bin/python dashboard.py -c endpoints_ecp.json -s ecp
