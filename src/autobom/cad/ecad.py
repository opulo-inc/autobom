# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, time, copy, shutil

from ..base.logger import Logger


class ECAD():

    def __init__(self, part_info, settings, sha, repoPath, abPath):

        self.part_info = part_info
        self.settings = settings
        self.path = None
        self.sha = sha
        self.name = self.part_info["name"]
        self.repoPath = repoPath
        self.abPath = abPath


    def out(self, manifest):
        
        #using default settings, but allowing part-specific to override
        render_method = self.settings["ecad"]["render"]
        if "render" in self.part_info:
            render_method = self.part_info["render"]

        export_method = self.settings["ecad"]["export"]
        if "export" in self.part_info:
            export_method = self.part_info["export"]


        # checking type

        if os.path.isfile(self.path + "/" + self.name + ".kicad_pro"):
            if self.outKicad(render_method, export_method, manifest):
                Logger.info(f"Exported and rendered {self.part_info['name']}")
            else:
                Logger.warn(f"Failed to export or render {self.part_info['name']}")

        else:
            Logger.warn(f'Found file {base}{ext} but {ext} files are not supported.')


    def outKicad(self, render_method, export_method, manifest):
        # Freecad exporting
    
        #================
        # Kick off rendering
        #================

        renderInputPath = self.abPath + "/renderQueue/kicad/in/" + self.name

        shutil.copytree(self.path, renderInputPath)

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
            render["img_path"] = "export/" + self.part_info["name"] + "/" + self.part_info["name"] + "-top.png"

        elif render_method == "img":
            render["method_preference"] = "img"
            render["img_path"] = "export/" + self.part_info["name"] + "/" + self.part_info["name"] + "-top.png"
        else:
            # just put whatever the user dropped in as the render link
            render["method_preference"] = "img"
            render["img_path"] = render_method

        part_manifest["render"] = render
        
        if export_method == "step":
            part_manifest["export"] = "export/" + self.part_info["name"] + ".step"
        elif export_method == "stl":
            part_manifest["export"] = "export/" + self.part_info["name"] + ".step"


        # waiting for source file to be deleted by render engine, indicating it's done, or exiting after timeout
        timeout = time.time() + 90
        while os.path.isdir(renderInputPath):
            time.sleep(0.2)
            if time.time() > timeout:
                return False
            
        # we're here if the source file was deleted within timeout
        # now we copy files over to export
        exportDir = self.abPath + "/renderQueue/kicad/out/" + self.name

        # Copy the file to the destination directory
        shutil.copytree(exportDir,  self.repoPath + "/autobom/export/" + self.name)

        shutil.rmtree(self.abPath + "/renderQueue/kicad/out/" + self.name)

        manifest["parts"].append(part_manifest)

        return True
        