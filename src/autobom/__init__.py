# -*- coding: utf-8 -*-
# Please don't import anything in this file to avoid issues when it is imported in setup.py

__version__ = '0.2.0'

CMD_NAME = 'autobom'  # Lower case command and module name
APP_NAME = 'AutoBOM'  # Application name in texts meant to be human readable
APP_URL = 'https://github.com/opulo-inc/autobom'

import logging
import os
import shutil
import sys

from .base.builder import Builder
from .base.config import ConfigError, OUTPUT_DIR, load_config, resolve_boms
from .base.logger import Logger
from .base.render_engines import managed_render_engines

def main():

    logging.basicConfig(level=logging.DEBUG)

    repo_path = os.environ.get('GITHUB_WORKSPACE', '.')
    try:
        boms = resolve_boms(load_config(repo_path))
    except ConfigError as e:
        Logger.warn(f"Invalid autobom.json: {e}")
        sys.exit(1)

    output_root = os.path.join(repo_path, OUTPUT_DIR)
    if os.path.exists(output_root):
        shutil.rmtree(output_root)

    results = []
    with managed_render_engines():
        for bom_id, config, out_dir in boms:
            builder = None
            try:
                builder = Builder(config, out_dir, bom_id)
                ok = builder.run()
            except Exception as e:
                Logger.warn(f"BOM {bom_id or config.get('bom_path')} failed: {e}")
                ok = False
            parts = len(builder.manifest.get("parts", [])) if builder else 0
            failures = len(builder.failures) if builder else 0
            results.append((bom_id, config.get("bom_path"), ok, parts, failures))

    if len(results) > 1:
        Logger.info("----- BOM summary -----")
        for bom_id, bom_path, ok, parts, failures in results:
            status = "ok" if ok else "FAILED"
            Logger.info(f"  {bom_id} ({bom_path}): {status}, {parts} parts, {failures} failure(s)")

    if not all(ok for _, _, ok, _, _ in results):
        sys.exit(1)

if __name__ == '__main__':
    main()
