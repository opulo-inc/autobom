# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, fnmatch, copy, subprocess, autobom, shutil

from ..base.logger import Logger

ecad_filetype = [
    ".kicad_pro"
]

class ECAD():

    def __init__(self, part_info, settings, sha):

        self.part_info = part_info
        self.settings = settings
        self.path = None
        self.sha = sha
        self.name = self.part_info["name"]

    def find(self):
        # this function hunts for the source file, based on the part name and type
        
        search_path = "."
        # if there is a path from settings, use it as starting search path.
        if "path" in self.settings["ecad"]:
            search_path = self.settings['ecad']["path"]
    
        for root, dirs, files in os.walk(search_path):
            for name in files:
                if fnmatch.fnmatch(name, self.part_info["name"] + ".kicad*"):
                    full_path = os.path.join(root, name)
                    base, ext = os.path.splitext(full_path)
                    if ext.lower() in ecad_filetype:
                        Logger.info(f"Found a source file match for {self.part_info['name']} with {name}.")
                        current = "./"
                        self.path = os.path.relpath(full_path, current)
                        return True

        return False


    def out(self, manifest):
        
        #using default settings, but allowing part-specific to override
        render_method = self.settings["ecad"]["render"]
        if "render" in self.part_info:
            render_method = self.part_info["render"]

        export_method = self.settings["ecad"]["export"]
        if "export" in self.part_info:
            export_method = self.part_info["export"]


        # checking type

        base, ext = os.path.splitext(self.path)

        if ext.lower() == ".kicad_pro":
            if self.outKicad(render_method, export_method, manifest):
                Logger.info(f"Exported and rendered {self.part_info['name']}")
            else:
                Logger.warn(f"Failed to export or render {self.part_info['name']}")

        else:
            Logger.warn(f'Found file {base}{ext} but {ext} files are not supported.')


    def outKicad(self, render_method, export_method, manifest):
        # Freecad exporting
        try:
            self.exportAndRenderFromKicad()

            # update manifest

            part_manifest = copy.deepcopy(self.part_info)

            render = {"method_preference": "", "img_path": "", "3d_path": ""}

            if render_method == "src":
                # this is easy, it's just pulling the github link! no sweat!
                repo = self.settings['source_url']

                ghlink = repo + "/blob/" + self.sha + "/" + self.path

                # correctly formatted gh link for reference
                # https://github.com/opulo-inc/lumenpnp/blob/be58b3eeba5aecb69e166f0e397c5b0ebc95fa33/pnp/cad/FDM/y-gantry.FCStd
                
                render["method_preference"] = "3d"
                render["3d_path"] = ghlink

            elif render_method == "img":
                render["method_preference"] = "img"
                render["img_path"] = "export/" + self.part_info["name"] + "/" + self.part_info["name"] + ".png"
            else:
                # just put whatever the user dropped in as the render link
                render["method_preference"] = "img"
                render["img_path"] = render_method

            part_manifest["render"] = render
            
            if export_method == "step":
                part_manifest["export"] = "export/" + self.part_info["name"] + ".step"
            elif export_method == "stl":
                part_manifest["export"] = "export/" + self.part_info["name"] + ".step"

            manifest["parts"].append(part_manifest)

            return True
        except Exception as e:
            print(e)
            return False
        
    def exportAndRenderFromKicad(self):

        base, ext = os.path.splitext(self.path)

        export_path = "autobom/export/" + str(self.name)
        os.makedirs(export_path)

        module_path = os.path.dirname(autobom.__file__)
        config_path = module_path + "/cad/config.kibot.yaml"
        
        subprocess.call(["kibot", "-c", config_path, "-e", self.name + ".kicad_sch", "-b", self.name + ".kicad_pcb", "-d", export_path ], stdout=subprocess.STDOUT, stderr=subprocess.STDOUT)

user=postgres.sszjvkzybnilulgqunlx password=[YOUR-PASSWORD] host=aws-0-us-east-2.pooler.supabase.com port=6543 dbname=postgres