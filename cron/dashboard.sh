#!/bin/bash

cd "$(dirname "$0")"
if [ ! -d log ]; then
    mkdir log
fi
/home/lukasz/2020.11.25_anl_dashboard/venv/bin/python dashboard.py -c endpoints_aps.json -s aps
/home/lukasz/2020.11.25_anl_dashboard/venv/bin/python dashboard.py -c endpoints_ecp.json -s ecp
