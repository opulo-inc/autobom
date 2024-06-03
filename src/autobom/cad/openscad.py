# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import glob
import subprocess
import os
import sys

class Openscad:
    def __init__(self) -> None:
        pass

    def render(self, name, path):

        file=os.path.abspath(path)
        print(file)

        f = open("autobom/render.scad", "w")
        f.write("import(\"")
        f.write(file)
        f.write("\", convexity=3);")
        f.close()
            
        subprocess.call(["openscad", "-o", "autobom/data/render/"+name+".png", "--quiet", "--render", "--projection=o", "--viewall","--colorscheme","BeforeDawn", "--imgsize", "1028,1028", "--hardwarnings", "autobom/render.scad" ])
        
        os.remove("autobom/render.scad")