# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, subprocess, shutil
from pathlib import Path

export_options = ["step", "stl", "all"]

kicadIn = "/renderQueue/kicad/in/"
kicadOut = "/renderQueue/kicad/out/"

def renderKicad(name, path):

    base, ext = os.path.splitext(path)

    export_path = kicadOut + str(name)

    # delete previous export dir if still there
    if os.path.exists(export_path) and os.path.isdir(export_path):
        shutil.rmtree(export_path)

    os.makedirs(export_path)

    config_path = "/autobom/src/autobom/render/config.kibot.yaml"

    justNeedsExt = path + "/" + name
    
    subprocess.call(["kibot", "-c", str(config_path), "-e", justNeedsExt + ".kicad_sch", "-b", justNeedsExt + ".kicad_pcb", "-d", export_path ])

while True:
    #check kicad
    kicadDirs = [ f.name for f in os.scandir(kicadIn) if f.is_dir() ]
    if kicadDirs != []:
        for directory in kicadDirs:
            print("found directory: " + str(directory) + "! processing...")
            path = kicadIn + directory
            renderKicad(directory, path)
            shutil.rmtree(path)
            print("done")

