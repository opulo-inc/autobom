#!/bin/sh
mkdir -p /renderQueue/wireviz/in /renderQueue/wireviz/out
cd /autobom/render
exec python wcad_renderer.py
