# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, copy, glob, sys, time, shutil

from ..base.logger import Logger

freecad_paths = [
    '/squashfs-root/usr/lib',
    '/home/runner/work/feeder/feeder/squashfs-root/usr/lib',  # For CI when using AppImage
    '/usr/lib/freecad/lib/',  # For CI
    '/usr/lib/freecad-daily-python3/lib/',  # For Ubuntu
    '/usr/lib64/freecad/lib64/',  # For Fedora
    '/Applications/FreeCAD.app/Contents/MacOS/',  # For Mac OS X
    '/Applications/FreeCAD.app/Contents/Resources/lib',  # For Mac OS X
    '/Applications/FreeCAD.app/Contents/Resources/lib/python3.10/site-packages'
    'c:/Program Files/FreeCAD 0.18/bin/',  # For Windows
    'c:/Program Files/FreeCAD 0.19/bin/',  # For Windows
]

for path in freecad_paths:
    if os.path.exists(path):
        sys.path.append(path)

import FreeCAD
import MeshPart

export_options = ["step", "stl", "all"]

class MCAD():

    def __init__(self, part_info, settings, sha, repoPath, abPath):

        self.part_info = part_info
        self.settings = settings
        self.path = None
        self.name = part_info["name"]
        self.sha = sha
        self.repoPath = repoPath
        self.abPath = abPath
            

    def out(self, manifest):
        
        #using default settings, but allowing part-specific to override
        render_method = self.settings["mcad"]["render"]
        if "render" in self.part_info:
            render_method = self.part_info["render"]

        export_method = self.settings["mcad"]["export"]
        if "export" in self.part_info:
            export_method = self.part_info["export"]

        # checking type

        base, ext = os.path.splitext(self.path)
        if ext.lower() == ".fcstd":
            if self.outFreecad(render_method, export_method, manifest):
                Logger.info(f"Exported and rendered {self.part_info['name']}")
            else:
                Logger.warn(f"Failed to export or render {self.part_info['name']}")

        elif ext.lower() == ".scad":
            if self.outOpenscad(render_method, export_method, manifest):
                Logger.info(f"Exported and rendered {self.part_info['name']}")
            else:
                Logger.warn(f"Failed to export or render {self.part_info['name']}")

        else:
            Logger.warn(f'Found file {base}{ext} but {ext} files are not supported.')


    def outFreecad(self, render_method, export_method, manifest):
        # Freecad exporting
        try:
            #================
            # Kick off rendering
            #================

            renderInputPath = self.abPath + "/renderQueue/freecad/in/"+self.name+".FCStd"

            print(shutil.copyfile(self.path, renderInputPath)) 


            #================
            # UPDATE MANIFEST
            #================

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
                render["img_path"] = "export/" + self.part_info["name"] + ".png"

            elif render_method == "img":
                render["method_preference"] = "img"
                render["img_path"] = "export/" + self.part_info["name"] + ".png"
            else:
                # just put whatever the user dropped in as the render link
                # TODO should download this and package this image locally
                render["method_preference"] = "img"
                render["img_path"] = render_method

            part_manifest["render"] = render
            
            if export_method == "step":
                part_manifest["export"] = "export/" + self.part_info["name"] + ".step"
            elif export_method == "stl":
                part_manifest["export"] = "export/" + self.part_info["name"] + ".stl"

            # waiting for source file to be deleted by render engine, indicating it's done, or exiting after timeout
            print("about to start timeout")
            timeout = time.time() + 90
            while os.path.isfile(renderInputPath):
                print("timeout ping")
                time.sleep(0.2)
                if time.time() > timeout:
                    return False
                
            print("python thinks the file is gone now")
                
            # we're here if the source file was deleted within timeout
            # now we copy files over to export
            exportFiles = os.listdir(self.abPath + "/renderQueue/freecad/out")

            for file in exportFiles:
                # Construct the full path to the source file
                source_file = os.path.join(self.abPath + "/renderQueue/freecad/out", file)

                # Copy the file to the destination directory
                shutil.copy(source_file,  self.repoPath + "/autobom/export")

                os.remove(source_file)

            manifest["parts"].append(part_manifest)

            return True
        except Exception as e:
            print(e)
            return False

    def outOpenscad(self, render_method, export_method, manifest):
        # Openscad exporting
        try:
            # choosing to force export and render for openscad regardless of settigngs
            # because there's really only one option for both
            # if export_method == "stl":
            #     scad.export()
            
            self.exportSTLFromOpenscad(self.part_info['name'], self.path)

            if render_method == "img":
                self.renderImageFromOpenscad(self.part_info['name'], self.path)

            
            # update manifest

            part_manifest = copy.deepcopy(self.part_info)

            render = {"method_preference": "", "img_path": "", "3d_path": ""}

            if render_method == "img":
                render["method_preference"] = "img"
                render["img_path"] = "export/" + self.part_info["name"] + ".png"
            else:
                # just put whatever the user dropped in as the render link
                render["method_preference"] = "img"
                render["img_path"] = render_method

            part_manifest["render"] = render
            
            if export_method == "stl":
                part_manifest["export"] = "export/" + self.part_info["name"] + ".stl"

            manifest["parts"].append(part_manifest)

            return True
        except:
            return False