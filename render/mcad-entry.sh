#!/bin/sh

mkdir -p /renderQueue/freecad/in /renderQueue/freecad/out \
         /renderQueue/openscad/in /renderQueue/openscad/out

Xvfb :5 -screen 0 800x600x24 &
export DISPLAY=:5
cd /autobom/render
exec uv run python mcad_renderer.py