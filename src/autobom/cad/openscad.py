# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import glob
import subprocess
import os
import sys

class Openscad:
    def __init__(self, name, path):
        self.name = name
        self.path = path

    @classmethod
    def renderFromSTL(self, name, stlPath):

        file=os.path.abspath(stlPath)

        f = open("autobom/render.scad", "w")
        f.write("import(\"")
        f.write(file)
        f.write("\", convexity=3);")
        f.close()
            
        subprocess.call(["openscad", "-o", "autobom/data/render/"+name+".png", "--quiet", "--render", "--projection=o", "--viewall","--colorscheme","BeforeDawn", "--imgsize", "1028,1028", "--hardwarnings", "autobom/render.scad" ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
        os.remove("autobom/render.scad")

    def export(self):
        # takes no arguments, can only export stl
        subprocess.call(["openscad", "--export-format", "asciistl", "-o", "autobom/data/export/"+self.name+".stl", self.path ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def render(self):
            
        subprocess.call(["openscad", "-o", "autobom/data/render/"+self.name+".png", "--quiet", "--render", "--projection=o", "--viewall","--colorscheme","BeforeDawn", "--imgsize", "1028,1028", "--hardwarnings", self.path ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
