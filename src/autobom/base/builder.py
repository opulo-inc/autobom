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

import enum, time, json, os, shutil, subprocess, autobom, fnmatch

from .logger import Logger
from .site import Site
from ..cad.mcad import MCAD
from ..cad.ecad import ECAD

default = {
    "colors": {
        "primary": "daa520",
        "secondary": "af8000"
    }
}

mcad_filetype = [
    ".fcstd",
    ".scad"
]

ecad_filetype = [
    ".kicad_pro"
]

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
    def __init__(self):
        super().__init__()

        # Getting github environment variables

        # self.abPath is the path to the contents of the autobom repository,
        # used mainly for copying web assets and sending files to the render engine
        self.abPath = os.environ.get('GITHUB_ACTION_PATH', '/Users/stephen/autobom')

        # self.repoPath is used to point towards where the repo itself is
        # this is less necessary as we could just write all paths in autobom
        # to be relative and assume we're running from there, but it's nice to be explicit
        self.repoPath = os.environ.get('GITHUB_WORKSPACE', '.')

        # change to repo dir just for the sake of sanity
        os.chdir(self.repoPath)

        # Load autobom config
        c = open(self.repoPath + '/autobom.json')
        config = json.load(c)

        # Load bom.json file
        b = open(self.repoPath + "/" + config["bom_path"])
        bom = json.load(b)

        self.config = config
        self.bom = bom
        self.manifest = {}
        self.site = Site(self.config["site"])
        
    def run(self):
        Logger.info("Autobom starting")
        # make autobom directory to start housing our goodies
        if os.path.exists("autobom"):
            # wipe autobom
            shutil.rmtree("autobom")

        os.makedirs(self.repoPath + "/autobom/export")

        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        shortsha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()

        # start adding to manifest object 
        self.manifest['build_init'] = time.time()
        self.manifest['bom'] = self.config["bom_path"]
        self.manifest['source_url'] = self.config["source_url"]
        self.manifest['name'] = self.bom['name']
        self.manifest['version'] = self.bom['version']
        self.manifest['shortsha'] = shortsha
        self.manifest['parts'] = []

        Logger.info(f'Building {self.manifest["name"]} - {self.manifest["version"]} - {shortsha}')
        Logger.info(f'Using BOM: {self.manifest["bom"]}')
        
        # iterating through parts
        for part in self.bom["parts"]:
            Logger.info("Now processing: " + part['name'])

            if part["type"] == "mcad":
                
                mcad = MCAD(part, self.config, sha, self.repoPath, self.abPath)
                if not self.findMcad(mcad):
                    Logger.warn("Was not able to find source file for " + part['name'])
                else:
                    mcad.out(self.manifest)

            elif part["type"] == "ecad":
                ecad = ECAD(part, self.config, sha, self.repoPath, self.abPath)
                if not self.findEcad(ecad):
                    Logger.warn("Was not able to find source file for " + part['name'])
                else:
                    ecad.out(self.manifest)

            elif part["type"] == "wcad":
                pass
            elif part["type"] == "misc":
                pass
            else:
                Logger.warn("Part type '" + str(part["type"]) + "' for " + str(part["name"]) + " is unknown. Skipping.")

        # save manifest to file
        with open(self.repoPath + "/autobom/manifest.json", "w") as outfile: 
            json.dump(self.manifest, outfile)

        self.renderSite()

        Logger.info("Autobom done!")
        

    def findMcad(self, mcad):
        # this function hunts for the source file, based on the part name and type
        
        search_path = self.repoPath
        # if there is a path from settings, use it as starting search path.
        if "path" in self.config["mcad"]:
            search_path = self.repoPath + "/" + self.config['mcad']["path"]
    
        for root, dirs, files in os.walk(search_path):
            for name in files:
                if fnmatch.fnmatch(name, mcad.part_info["name"] + ".*"):
                    full_path = os.path.join(root, name)
                    base, ext = os.path.splitext(full_path)
                    if ext.lower() in mcad_filetype:
                        Logger.info(f"Found a source file match for {mcad.part_info['name']} with {name}.")
                        mcad.path = full_path
                        return mcad.path

        return False
    
    def findEcad(self, ecad):
        # this function hunts for the source file, based on the part name and type
        
        search_path = self.repoPath
        # if there is a path from settings, use it as starting search path.
        if "path" in self.config["ecad"]:
            search_path = self.repoPath + "/" + self.config['ecad']["path"]
    
        for root, dirs, files in os.walk(search_path):
            for name in files:
                if fnmatch.fnmatch(name, ecad.part_info["name"] + ".kicad*"):
                    full_path = os.path.join(root, name)
                    base, ext = os.path.splitext(full_path)
                    if ext.lower() in ecad_filetype:
                        ecad.path = os.path.dirname(full_path)
                        Logger.info(f"Found a source file match for {ecad.part_info['name']} with {name}.")
                        return ecad.path

        return False

    def renderSite(self):

        self.settings = {**default, **self.config}

        # copying over web assets
        shutil.copytree(self.abPath + "/src/autobom/web", "autobom/web")

        # make html file that will become our BOM
        f = open(self.repoPath + "/autobom/index.html", "w")

        f.write(header)

        githubLink = self.manifest["source_url"]
        gitCommit = self.manifest['shortsha']

        title = "<h1>" + str(self.manifest["name"]) + " BOM - " + str(self.manifest["version"]) + "</h1>"
        source = "<a href='" + githubLink + "' target='_blank' rel='noopener noreferrer'><h4>" + gitCommit + "</h4></a>"

        f.write(title)
        f.write(source)

        #write the beginning of table, and row for header
        f.write(bulk)

        for part in self.manifest["parts"]:

            row = f"""
            <tr id="{part["name"]}"
            renderpreference="{part["render"]["method_preference"]}"
            3dpath="{part["render"]["3d_path"]}"
            imgpath="{part["render"]["img_path"]}"
            onclick="updateRender(this)"><th>{part["name"]} 
            </th><th>{part["quantity"]}
            </th><th><a href="{part["source"]}">Link</a>
            </th><th>{part["notes"]}
            </th></tr>
            """
                
            f.write(row)

        f.write(footer)

        f.close()


header = """
<!DOCTYPE html>
<head>
    <link rel="stylesheet" href="web/style.css">
    <script src="web/kicanvas.js"></script>
    <script type="text/javascript" src="web/o3dv/o3dv.min.js"></script>
    <script src="web/main.js"></script>
</head>
<body>
    <div id="header">
""";



bulk = """        
    </div>
    <div id="bulk">
    
        <div id="bom-items">
            <table>

                <tr class="titlerow">
                    <th>Name</th>
                    <th>Quantity</th>
                    <th>Source</th>
                    <th>Notes</th>
                </tr>
""";

footer = """
            </table>
        </div>
        <div id="render">
            
            <div id="replace-with-render"><p style="margin-top:45%;">Click an item to view</p></div>
            <div id="notes-render">notes</div>
        </div>
    </div>
</body>
""";


