# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import math
import os
import sys
import traceback
from pathlib import Path
from typing import List
import time

freecad_paths = [
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
        print(f"Added possible FreeCAD path: {path}")
        sys.path.append(path)

import FreeCAD
import MeshPart

export_options = ["step", "stl", "all"]

class Freecad():

    def __init__(self, name, path):
        self.name = name
        self.path = path

    def export(self, type):

        if type not in export_options:
            return False
        
        print("Processing " + self.name)

        doc = FreeCAD.open(self.path)

        name = self.name

        body = [obj for obj in doc.Objects if obj.Label == "Body"]

        if len(body) == 0:
            print(f"Cannot find body object. {len(doc.Objects)} objects present")
            for obj in doc.Objects:
                print(f"- {obj.Label}")

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
                print(f"\tCorrected '{obj.Label}' font file name from {font_file_property}")
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
        print(f"\tRecompute of model took {total:3f}s")

        shape = body.Shape.copy(False)

        if type == "step" or type == "all":
            shape.exportStep("autobom/data/export/" + name + ".step")
            print("exported step")

        if type == "stl" or type == "all":
            # Generate STL
            mesh = doc.addObject("Mesh::Feature", "Mesh")
            mesh.Mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.025, Relative=False)
            mesh.Mesh.write("autobom/data/export/" + name + ".stl")
        
        FreeCAD.closeDocument(doc.Name)

