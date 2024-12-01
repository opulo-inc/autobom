# -*- coding: utf-8 -*-
# Please don't import anything in this file to avoid issues when it is imported in setup.py

__version__ = '0.3.2'

CMD_NAME = 'autobom'  # Lower case command and module name
APP_NAME = 'AutoBOM'  # Application name in texts meant to be human readable
APP_URL = 'https://github.com/opulo-inc/autobom'

import json, sys, os

from .base.builder import Builder

def main():

    builder = Builder()

    builder.run()    

if __name__ == '__main__':
    main()