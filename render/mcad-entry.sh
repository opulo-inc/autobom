#!/bin/sh

Xvfb :5 -screen 0 800x600x24 &
export DISPLAY=:5
cd /autobom/render
uv run mcad_renderer.py