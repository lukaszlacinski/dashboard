#!/bin/bash

cd "$(dirname "$0")"
if [ ! -d log ]; then
    mkdir log
fi
LOGLEVEL=INFO /home/lukasz/2020.11.25_anl_speedpage/venv/bin/python speedpage_mt.py -c endpoints_aps.json -s aps
LOGLEVEL=INFO /home/lukasz/2020.11.25_anl_speedpage/venv/bin/python speedpage_mt.py -c endpoints_ecp.json -s ecp
