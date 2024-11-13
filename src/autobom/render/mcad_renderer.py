# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, subprocess, sys, time
from pathlib import Path

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

processed = []

freecadIn = "/renderQueue/freecad/in/"
freecadOut = "/renderQueue/freecad/out/"

openscadIn = "/renderQueue/openscad/in/"
openscadOut = "/renderQueue/openscad/out/"

def renderFreecad(path):

    # we just barf out an stl, step, and image

    doc = FreeCAD.open(path)

    name = Path(path).stem

    body = [obj for obj in doc.Objects if obj.Label == "Body"]

    if len(body) == 0:
        #print(f"Cannot find body object. {len(doc.Objects)} objects present")

        raise Exception(f"Object named 'Body' not found in model {name}")

    body = body[0]

    # Find font references in the model and ensure they point to the correct font file
    fonts = [obj for obj in doc.Objects if
            obj.isDerivedFrom("Part::Part2DObject") and hasattr(obj, "FontFile")]

    # for obj in fonts:
    #     font_file_property = obj.getPropertyByName('FontFile')
    #     new_font_file = os.path.join(font_folder, os.path.split(font_file_property)[1])
    #     if not os.path.isfile(new_font_file):
    #         raise FileNotFoundError(f"Cannot find font file {new_font_file}")

    #     if new_font_file != font_file_property:
    #         setattr(obj, "FontFile", new_font_file)
    #         obj.touch()

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

    # generate STEP
    shape.exportStep(freecadOut + name + ".step")

    # Generate STL
    mesh = doc.addObject("Mesh::Feature", "Mesh")
    mesh.Mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.025, Relative=False)
    mesh.Mesh.write(freecadOut + name + ".stl")

    time.sleep(1)

    _renderImageFromSTL(name, freecadOut + name + ".stl", freecadOut)
    
    FreeCAD.closeDocument(doc.Name)

def renderOpenscad(path):
    _renderSTLFromOpenscad(path)
    _renderImageFromOpenscad(path)

def _renderImageFromSTL(name, stlPath, outPath):

    file=os.path.abspath(stlPath)

    f = open(outPath+"render.scad", "w")
    f.write("import(\"")
    f.write(stlPath)
    f.write("\", convexity=3);")
    f.close()

    print("made openscad file, time to render image")
        
    subprocess.call(["openscad", "-o", outPath+name+".png", "--quiet", "--render", "--projection=o", "--viewall","--colorscheme","BeforeDawn", "--imgsize", "1028,1028", "--hardwarnings", outPath+"render.scad" ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    os.remove(outPath+"render.scad")

def _renderSTLFromOpenscad(path):
    # takes no arguments, can only export stl
    name = os.path.splitext(os.path.basename(path))[0]
    subprocess.call(["openscad", "-o", openscadOut+name+".stl", path ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

def _renderImageFromOpenscad(path):
    name = os.path.splitext(os.path.basename(path))[0]
    subprocess.call(["openscad", "-o", openscadOut+name+".png", "--quiet", "--render", "--projection=o", "--viewall","--colorscheme","BeforeDawn", "--imgsize", "1028,1028", "--hardwarnings", path ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

while True:
    #check freecad first
    freecadFiles = [f for f in os.listdir(freecadIn) if f.lower().endswith(".fcstd")]
    if freecadFiles != []:
        for file in freecadFiles:
            if file not in processed:
                print("found file: " + str(file) + "! processing...")
                path = freecadIn + file
                renderFreecad(path)
                os.remove(path)
                processed.append(file)
                print("done")

    # check openscad second
    openscadFiles = [f for f in os.listdir(openscadIn) if f.lower().endswith(".scad")]
    if openscadFiles != []:
        for file in openscadFiles:
            if file not in processed:
                print("found file: " + str(file) + "! processing...")
                path = openscadIn + file
                renderOpenscad(path)
                os.remove(path)
                processed.append(file)
                print("done")
