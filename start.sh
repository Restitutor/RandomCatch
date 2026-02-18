#!/bin/bash

# Change to the directory of the script
cd "$(dirname "${BASH_SOURCE[0]}")"
uv run ./main.py
wait
