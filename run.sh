#!/bin/bash

set -e

cd /home/app

# Activate virtual environment
source ~/venv/main/bin/activate

export PATH="/usr/local/go/bin:$PATH"
nice -n 19 python3 run.py
