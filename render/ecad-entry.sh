#!/bin/sh

mkdir -p /renderQueue/kicad/in /renderQueue/kicad/out
cd /autobom/render
exec uv run python ecad_renderer.py