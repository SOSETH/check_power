#!/bin/sh

# This is very ugly. If you know of a python way to pack everything into a single *executable* file, feel free to fix this

echo "#!/usr/bin/env python3" > check_power.py
cat main.py >> check_power.py
cat NETTRACK-E3METER-SNMP-MIB.py >> check_power.py