# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

"""
The Logger class just makes things print to the command line nice and pretty.
"""

import datetime

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class Logger:
    def __init__(self):
        pass

    @classmethod
    def warn(self, msg):
        print(f"{bcolors.WARNING}WARN{bcolors.ENDC}" + " - " + str(datetime.datetime.now()) + " - " + msg)

    @classmethod
    def info(self, msg):
        print(f"{bcolors.OKCYAN}INFO{bcolors.ENDC}" + " - " + str(datetime.datetime.now()) + " - " + msg)