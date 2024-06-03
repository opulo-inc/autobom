# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, fnmatch, copy

from .freecad import Freecad
from .openscad import Openscad

class MCAD():

    def __init__(self, part_info, settings):

        self.part_info = part_info
        self.settings = settings
        self.path = None

    def find(self):
        # this function hunts for the source file, based on the part name and type
        
        search_path = "."
        # if there is a path from settings, use it as starting search path.
        if "path" in self.settings["mcad"]:
            search_path = self.settings['mcad']["path"]

        pattern = self.part_info["name"] + ".*"
        
        for root, dirs, files in os.walk(search_path):
            for name in files:
                if fnmatch.fnmatch(name, pattern):
                    full_path = os.path.join(root, name)
                    current = "./"
                    self.path = os.path.relpath(full_path, current)
                    return self.path

        return False


    def out(self, sha, manifest):
        
        #using default settings, but allowing part-specific to override
        render_method = self.settings["mcad"]["render"]
        if "render" in self.part_info:
            render_method = self.part_info["render"]

        export_method = self.settings["mcad"]["export"]
        if "export" in self.part_info:
            export_method = self.part_info["export"]

        # Freecad exporting

        fcstd = Freecad(self.part_info["name"], self.path)

        # the only condition that requires both stl and step export
        if export_method == "step" and render_method == "img":
            fcstd.export("all")

        elif export_method == "step" and render_method != "img":
            fcstd.export("step")

        elif export_method == "stl" or render_method == "img":
            fcstd.export("stl")

        # openscad image rendering
        if render_method == "img":
            scad = Openscad()
            stlPath = "autobom/data/export/" + self.part_info["name"] + ".stl"
            print(stlPath)
            scad.render(self.part_info["name"], stlPath)

            if render_method == "img" and export_method != "stl":
                #deleting stl if we didnt ask to export it specifically
                os.remove("autobom/data/export/" + self.part_info["name"] + ".stl")
        
        # update manifest

        part_manifest = copy.deepcopy(self.part_info)

        render = {"method": "", "path": ""}

        if render_method == "src":
            # this is easy, it's just pulling the github link! no sweat!
            repo = self.settings['gh-repo']

            ghlink = repo + "/blob/" + sha + "/" + self.path

            # correctly formatted gh link for reference
            # https://github.com/opulo-inc/lumenpnp/blob/be58b3eeba5aecb69e166f0e397c5b0ebc95fa33/pnp/cad/FDM/y-gantry.FCStd
            
            render["method"] = "3d"
            render["path"] = ghlink

        elif render_method == "img":
            render["method"] = "img"
            render["path"] = "data/render/" + self.part_info["name"] + ".png"
        else:
            # just put whatever the user dropped in as the render link
            render["method"] = "img"
            render["path"] = render_method

        part_manifest["render"] = render
        
        if export_method == "step":
            part_manifest["export"] = "data/export/" + self.part_info["name"] + ".step"
        elif export_method == "stl":
            part_manifest["export"] = "data/export/" + self.part_info["name"] + ".step"

        manifest["parts"].append(part_manifest)
            

        
