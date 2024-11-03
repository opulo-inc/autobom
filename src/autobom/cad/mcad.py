# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, fnmatch, copy, subprocess, sys, time

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

mcad_filetype = [
    ".fcstd",
    ".scad"
]

for path in freecad_paths:
    if os.path.exists(path):
        sys.path.append(path)

import FreeCAD
import MeshPart

export_options = ["step", "stl", "all"]

class MCAD():

    def __init__(self, part_info, settings, sha):

        self.part_info = part_info
        self.settings = settings
        self.path = None
        self.name = part_info["name"]
        self.sha = sha

    def find(self):
        # this function hunts for the source file, based on the part name and type
        
        search_path = "."
        # if there is a path from settings, use it as starting search path.
        if "path" in self.settings["mcad"]:
            search_path = self.settings['mcad']["path"]
    
        for root, dirs, files in os.walk(search_path):
            for name in files:
                if fnmatch.fnmatch(name, self.part_info["name"] + ".*"):
                    full_path = os.path.join(root, name)
                    base, ext = os.path.splitext(full_path)
                    if ext.lower() in mcad_filetype:
                        Logger.info(f"Found a source file match for {self.part_info['name']} with {name}.")
                        current = "./"
                        self.path = os.path.relpath(full_path, current)
                        return self.path

        return False


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
            # if they want a step, we need to export a step
            if export_method == "step":
                self.exportFromFreecad("all")

            elif export_method == "stl":
                self.exportFromFreecad("stl")


            # Rendering an image from STL
            # we ALWAYS do this, because even if the user selected 3d as their
            # render type, we package an image in case of being offline

            #making temporary openscad object just for rendering
            stlPath = "autobom/export/" + self.part_info["name"] + ".stl"
            self.renderImageFromSTL(self.part_info["name"], stlPath)

            if render_method == "img" and export_method != "stl":
                #deleting stl if we didnt ask to export it specifically
                os.remove("autobom/export/" + self.part_info["name"] + ".stl")
        
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
        
    def renderImageFromSTL(self, name, stlPath):

        file=os.path.abspath(stlPath)

        f = open("autobom/render.scad", "w")
        f.write("import(\"")
        f.write(file)
        f.write("\", convexity=3);")
        f.close()
            
        subprocess.call(["openscad", "-o", "autobom/export/"+name+".png", "--quiet", "--render", "--projection=o", "--viewall","--colorscheme","BeforeDawn", "--imgsize", "1028,1028", "--hardwarnings", "autobom/render.scad" ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
        os.remove("autobom/render.scad")

    def exportSTLFromOpenscad(self, name, path):
        # takes no arguments, can only export stl
        subprocess.call(["openscad", "--export-format", "asciistl", "-o", "autobom/data/export/"+name+".stl", path ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def renderImageFromOpenscad(self, name, path):
            
        subprocess.call(["openscad", "-o", "autobom/export/"+name+".png", "--quiet", "--render", "--projection=o", "--viewall","--colorscheme","BeforeDawn", "--imgsize", "1028,1028", "--hardwarnings", path ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def exportFromFreecad(self, type):

        if type not in export_options:
            return False

        doc = FreeCAD.open(self.path)

        name = self.name

        body = [obj for obj in doc.Objects if obj.Label == "Body"]

        if len(body) == 0:
            #print(f"Cannot find body object. {len(doc.Objects)} objects present")

            raise Exception(f"Object named 'Body' not found in model {self.path.name}")

        body = body[0]

        # Find font references in the model and ensure they point to the correct font file
        fonts = [obj for obj in doc.Objects if
                obj.isDerivedFrom("Part::Part2DObject") and hasattr(obj, "FontFile")]

        for obj in fonts:
            font_file_property = obj.getPropertyByName('FontFile')
            new_font_file = os.path.join(font_folder, os.path.split(font_file_property)[1])
            if not os.path.isfile(new_font_file):
                raise FileNotFoundError(f"Cannot find font file {new_font_file}")

            if new_font_file != font_file_property:
                setattr(obj, "FontFile", new_font_file)
                obj.touch()

        # Recompute the model to ensure its valid and does not contain broken references or edges
        # Mark each object as "changed"
        for obj in doc.Objects:
            obj.touch()

        # Recompute the entire document
        t0 = time.perf_counter()
        doc.recompute(None, True, True)
        t1 = time.perf_counter()
        total = t1 - t0
        #print(f"\tRecompute of model took {total:3f}s")

        shape = body.Shape.copy(False)

        if type == "step" or type == "all":
            shape.exportStep("autobom/export/" + name + ".step")

        if type == "stl" or type == "all":
            # Generate STL
            mesh = doc.addObject("Mesh::Feature", "Mesh")
            mesh.Mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.025, Relative=False)
            mesh.Mesh.write("autobom/export/" + name + ".stl")
        
        FreeCAD.closeDocument(doc.Name)