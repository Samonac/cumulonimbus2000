#!/usr/bin/env python3.5
#-- coding: utf-8 --

import requests
from datetime import datetime, timedelta
import sys

# TODO :
#  'control_hue': 'hue_XX'

def main(task={}):
    print('In Control_HUE for task : {}'.format(task))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main(task={"action": 1, "weight": 5})  # Action = badgeNumber ; weight = how many consecutive times it was scanned in past 5 seconds (1 to 10)
        print('Usage: python script.py <task={"action": 1, "weight": 5}>')
