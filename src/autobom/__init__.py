# -*- coding: utf-8 -*-
# Please don't import anything in this file to avoid issues when it is imported in setup.py

__version__ = '0.2.0'

CMD_NAME = 'autobom'  # Lower case command and module name
APP_NAME = 'AutoBOM'  # Application name in texts meant to be human readable
APP_URL = 'https://github.com/opulo-inc/autobom'

import logging
import sys

from .base.builder import Builder
from .base.render_engines import managed_render_engines

def main():

    logging.basicConfig(level=logging.DEBUG)

    ok = False
    with managed_render_engines():
        builder = Builder()
        ok = builder.run()

    if not ok:
        sys.exit(1)

if __name__ == '__main__':
    main()
