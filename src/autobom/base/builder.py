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

import copy, enum, time, json, os, shutil, subprocess, autobom, fnmatch

from .logger import Logger
from .site import Site
from ..cad.mcad import MCAD, raw_source_url
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
        self.abPath = os.environ.get('GITHUB_ACTION_PATH')
        if not self.abPath:
            # Local fallback: package lives at <repo>/src/autobom/
            self.abPath = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(autobom.__file__))))

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
        if os.path.exists(self.repoPath + "/autobom"):
            # wipe autobom
            shutil.rmtree(self.repoPath + "/autobom")

        os.makedirs(self.repoPath + "/autobom/export")

        Logger.info(f"Autobom Path: {self.abPath}")
        Logger.info(f"Repository Path: {self.repoPath}")

        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        shortsha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        version = self._resolve_version(shortsha)

        # start adding to manifest object 
        self.manifest['build_init'] = time.time()
        self.manifest['bom'] = self.config["bom_path"]
        self.manifest['source_url'] = self.config["source_url"]
        self.manifest['name'] = self.bom['name']
        self.manifest['version'] = version
        self.manifest['shortsha'] = shortsha
        self.manifest['sha'] = sha
        self.manifest['parts'] = []

        Logger.info(f'Building {self.manifest["name"]} - {version}')
        Logger.info(f'Using BOM: {self.manifest["bom"]}')
        
        # iterating through parts
        failures = []
        missing_sources = []
        for part in self.bom["parts"]:
            Logger.info("Now processing: " + part['name'])
            source_path = None

            if part["type"] == "mcad":
                
                mcad = MCAD(part, self.config, sha, self.repoPath, self.abPath)
                if not self.findMcad(mcad):
                    msg = "Was not able to find source file for " + part['name']
                    Logger.warn(msg)
                    failures.append(msg)
                    missing_sources.append((part['name'], 'mcad'))
                else:
                    source_path = mcad.path
                    if not mcad.out(self.manifest):
                        failures.append(f"Failed to export or render {part['name']}")

            elif part["type"] == "ecad":
                ecad = ECAD(part, self.config, sha, self.repoPath, self.abPath)
                if not self.findEcad(ecad):
                    msg = "Was not able to find source file for " + part['name']
                    Logger.warn(msg)
                    failures.append(msg)
                    missing_sources.append((part['name'], 'ecad'))
                else:
                    source_path = os.path.join(ecad.path, part['name'] + ".kicad_pcb")
                    if not ecad.out(self.manifest):
                        failures.append(f"Failed to export or render {part['name']}")

            elif part["type"] == "wcad":
                pass
            elif part["type"] == "misc":
                pass
            else:
                Logger.warn("Part type '" + str(part["type"]) + "' for " + str(part["name"]) + " is unknown. Skipping.")

            # Always list the part on the site, even if export/render failed
            self._ensure_part_listed(part, sha, source_path)

        # save manifest to file
        with open(self.repoPath + "/autobom/manifest.json", "w") as outfile: 
            json.dump(self.manifest, outfile)

        self.renderSite()

        self._report_bom_coverage(missing_sources)

        if failures:
            for failure in failures:
                Logger.warn(failure)
            Logger.warn(f"Autobom finished with {len(failures)} failure(s)")
            # Default is not strict: a partial export still counts as success.
            # Set "strict": true in autobom.json to fail the job on any part error.
            if self.config.get("strict", False):
                return False
            Logger.info("Ignoring part failures because autobom.json strict is not true")
            return True

        Logger.info("Autobom done!")
        return True

    def _resolve_version(self, shortsha):
        """Release tag on GitHub release runs; git short hash otherwise."""
        if os.environ.get("GITHUB_EVENT_NAME") == "release":
            tag = os.environ.get("GITHUB_REF_NAME")
            if not tag:
                ref = os.environ.get("GITHUB_REF", "")
                if ref.startswith("refs/tags/"):
                    tag = ref[len("refs/tags/"):]
            if tag:
                return tag
        return shortsha

    def _ensure_part_listed(self, part, sha, source_path):
        """Add a BOM part to the manifest if export did not already record it."""
        for existing in self.manifest["parts"]:
            if existing.get("name") == part["name"] and existing.get("type") == part.get("type"):
                return

        entry = copy.deepcopy(part)
        render = {"method_preference": "", "img_path": "", "3d_path": "", "kicad_path": ""}
        ptype = part.get("type")
        if ptype == "mcad":
            method = part.get("render", self.config.get("mcad", {}).get("render", "src"))
            render["img_path"] = "export/" + part["name"] + ".png"
            if method == "src" and source_path:
                render["method_preference"] = "3d"
                render["3d_path"] = raw_source_url(
                    self.config.get("source_url", ""), sha, self.repoPath, source_path
                )
            elif method == "img":
                render["method_preference"] = "img"
            else:
                render["method_preference"] = "img"
                if method not in ("src", "img"):
                    render["img_path"] = method
        elif ptype == "ecad":
            method = part.get("render", self.config.get("ecad", {}).get("render", "src"))
            render["img_path"] = "export/" + part["name"] + "/" + part["name"] + "-top.png"
            if source_path:
                render["kicad_path"] = raw_source_url(
                    self.config.get("source_url", ""), sha, self.repoPath, source_path
                )
            if method == "src":
                render["method_preference"] = "kicanvas"
            elif method == "img":
                render["method_preference"] = "img"
            else:
                render["method_preference"] = "img"
                render["img_path"] = method
        entry["render"] = render
        self.manifest["parts"].append(entry)

    def _mcad_search_root(self):
        if "path" in self.config.get("mcad", {}):
            return os.path.join(self.repoPath, self.config["mcad"]["path"])
        return self.repoPath

    def _ecad_search_root(self):
        if "path" in self.config.get("ecad", {}):
            return os.path.join(self.repoPath, self.config["ecad"]["path"])
        return self.repoPath

    def _skip_source_dir(self, dirname):
        skip = {".git", "backups", "__pycache__", "renderQueue", "autobom", "index.3dshapes"}
        return dirname in skip or dirname.endswith("-backups") or dirname.endswith(".3dshapes")

    def _unused_source_files(self, search_path, extensions):
        unused = []
        bom_names = {part["name"].lower() for part in self.bom["parts"]}
        if not os.path.isdir(search_path):
            return unused
        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if not self._skip_source_dir(d)]
            if any(self._skip_source_dir(part) for part in root.split(os.sep)):
                continue
            for name in files:
                base, ext = os.path.splitext(name)
                if ext.lower() not in extensions:
                    continue
                if base.lower() not in bom_names:
                    unused.append(os.path.relpath(os.path.join(root, name), self.repoPath))
        return sorted(unused)

    def _report_bom_coverage(self, missing_sources):
        unused_mcad = self._unused_source_files(self._mcad_search_root(), mcad_filetype)
        unused_ecad = self._unused_source_files(self._ecad_search_root(), ecad_filetype)

        Logger.info("----- BOM coverage -----")
        if unused_mcad:
            Logger.info(f"MCAD files in the repo not listed in the BOM ({len(unused_mcad)}):")
            for path in unused_mcad:
                Logger.info(f"  {path}")
        else:
            Logger.info("MCAD files in the repo not listed in the BOM: none")

        if unused_ecad:
            Logger.info(f"ECAD files in the repo not listed in the BOM ({len(unused_ecad)}):")
            for path in unused_ecad:
                Logger.info(f"  {path}")
        else:
            Logger.info("ECAD files in the repo not listed in the BOM: none")

        if missing_sources:
            Logger.info(f"BOM parts with no source file ({len(missing_sources)}):")
            for name, ptype in missing_sources:
                Logger.info(f"  {name} ({ptype})")
        else:
            Logger.info("BOM parts with no source file: none")
        Logger.info("------------------------")
        

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
                        Logger.info(f"Found a source file match for {mcad.part_info['name']} with name {name}.")
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

    def _source_links(self, source):
        if isinstance(source, (list, tuple)):
            urls = [u for u in source if u]
        elif source:
            urls = [source]
        else:
            return ""
        if len(urls) == 1:
            return f'<a href="{urls[0]}" target="_blank" rel="noopener noreferrer">Link</a>'
        return " ".join(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">Link {i}</a>'
            for i, url in enumerate(urls, 1)
        )

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

            render = part.get("render") or {}
            row = f"""
            <tr id="{part["name"]}"
            renderpreference="{render.get("method_preference", "")}"
            3dpath="{render.get("3d_path", "")}"
            kipath="{render.get("kicad_path", "")}"
            imgpath="{render.get("img_path", "")}"
            onclick="updateRender(this)"><th>{part["name"]} 
            </th><th>{part["quantity"]}
            </th><th>{self._source_links(part.get("source"))}
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
            <div id="render-toolbar" hidden>
                <button type="button" id="view-src" class="view-toggle">Source</button>
                <button type="button" id="view-img" class="view-toggle">Image</button>
            </div>
            <div id="replace-with-render"><p style="margin-top:45%;">Click an item to view</p></div>
        </div>
    </div>
</body>
""";


