# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

"""
The Builder class is the main thing responsible for parsing the bom.json file and building an export zip. It handles:

- getting the manifest.json generated
- getting all renders made and stored correctly
- getting all exports made and stored correctly
- getting the website built
"""

import enum, time, json, os, shutil, subprocess

from .logger import Logger
from .site import Site
from ..cad.mcad import MCAD

class McadExportTypes(enum.IntEnum):
    NONE = 0
    STEP = 1
    STL = 2

class McadRenderTypes(enum.IntEnum):
    NONE = 0
    SRC = 1
    IMAGE = 2

class EcadExportTypes(enum.IntEnum):
    NONE = 0
    GERBER = 1

class EcadRenderTypes(enum.IntEnum):
    NONE = 0
    SRC = 1
    IMAGE = 2
    

class Builder:
    def __init__(self, config, bom):
        super().__init__()

        self.config = config
        self.bom = bom
        self.manifest = {}

        self.log = Logger()
        self.site = Site(self.config["site"])
        
        
    def run(self):
        # make autobom directory to start housing our goodies
        if os.path.exists("autobom"):
            print("Directory 'autobom' already exists, wiping")
            # wipe autobom
            shutil.rmtree("autobom")

        os.makedirs("autobom/data/render")
        os.makedirs("autobom/data/export")
        print("Directory 'autobom' created")

        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        shortsha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()

        # start adding to manifest object 
        self.manifest['build_init'] = time.time()
        self.manifest['bom'] = self.config["bom_path"]
        self.manifest['name'] = self.bom['name']
        self.manifest['version'] = self.bom['version']
        self.manifest['shortsha'] = shortsha
        self.manifest['parts'] = []
        
        # iterating through parts
        for part in self.bom["parts"]:
            print("Now processing: " + part['name'])

            if part["type"] == "mcad":
                
                mcad = MCAD(part, self.config)
                if not mcad.find():
                    self.log.warn("Was not able to find source file for " + part['name'])
                else:
                
                    mcad_render_status = mcad.out(sha, self.manifest)

                    #based on what came out, we add to manifest 




            elif part["type"] == "ecad":
                pass
            elif part["type"] == "wcad":
                pass
            elif part["type"] == "misc":
                pass
            else:
                self.log.warn("Part type '" + str(part["type"]) + "' for " + str(part["name"]) + " is unknown. Skipping.")

        # save manifest to file
        with open("autobom/data/manifest.json", "w") as outfile: 
            json.dump(self.manifest, outfile)

        self.site.build(self.manifest)

        
        # zip up the folder

