# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

"""
The Logger class just makes things print to the command line nice and pretty.
"""

import datetime

class Logger:
    def __init__(self):
        pass

    def warn(self, msg):
        print("WARN - " + str(datetime.datetime.now()) + " - " + msg)
    def info(self, msg):
        print("INFO - " + str(datetime.datetime.now()) + " - " + msg)