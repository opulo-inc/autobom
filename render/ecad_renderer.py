# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, subprocess, shutil, time
from pathlib import Path

export_options = ["step", "stl", "all"]

kicadIn = "/renderQueue/kicad/in/"
kicadOut = "/renderQueue/kicad/out/"

def renderKicad(path, name):

    export_path = kicadOut + name

    # delete previous export dir if still there
    if os.path.exists(export_path) and os.path.isdir(export_path):
        shutil.rmtree(export_path)

    os.makedirs(export_path)

    config_path = "/autobom/render/config.kibot.yaml"

    justNeedsExt = path + "/" + name
    
    subprocess.call(["kibot", "-c", str(config_path), "-e", justNeedsExt + ".kicad_sch", "-b", justNeedsExt + ".kicad_pcb", "-d", export_path ])

while True:
    #check kicad
    kicadDirs = [ f.name for f in os.scandir(kicadIn) if f.is_dir() ]
    if kicadDirs != []:
        for name in kicadDirs:
            print("found directory: " + str(name) + "! processing...")
            path = kicadIn + name

            time.sleep(2)

            try:
                renderKicad(path, name)
                shutil.rmtree(path)
            except:
                shutil.rmtree(path)
                print("render failed")

