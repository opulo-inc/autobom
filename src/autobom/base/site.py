# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

"""
The Site class builds the standalone html page! It takes in the builder.web_data list, and generates an html page from there.
"""

import autobom, os, shutil

default = {
    "colors": {
        "primary": "daa520",
        "secondary": "af8000"
    }
}

class Site():
    def __init__(self, config):
        # updating default settings based on any config in autobom.json
        self.settings = {**default, **config}

    def build(self, manifest):

        # copying over web assets
        module_path = os.path.dirname(autobom.__file__)
        print(shutil.copytree(module_path + "/web", "autobom/data/web"))

        # make html file that will become our BOM
        f = open("autobom/index.html", "w")

        f.write(header)

        githubLink = "whoknows"
        gitcommit = "whatever"

        title = "<h1>" + str(manifest["name"]) + " BOM - " + str(manifest["version"]) + "</h1>"
        source = "<a href='" + githubLink + "' target='_blank' rel='noopener noreferrer'><h4>" + gitcommit + "</h4></a>"

        f.write(title)
        f.write(source)

        #write the beginning of table, and row for header
        f.write(bulk)

        for part in manifest["parts"]:

            row = f"""
            <tr id="{part["name"]}"
            rendertype="{part["render"]["method"]}"
            renderpath="{part["render"]["path"]}"
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
    <link rel="stylesheet" href="data/web/style.css">
    <script src="data/web/kicanvas.js"></script>
    <script type="text/javascript" src="data/web/o3dv/o3dv.min.js"></script>
    <script src="data/web/main.js"></script>
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

# <script>
#         render_data = {
#             "y-gantry": {
#                 "type": "3d",
#                 "path": "https://github.com/opulo-inc/lumenpnp/blob/main/pnp/cad/FDM/y-gantry.FCStd"
#             },
#             "ring-light": {
#                 "type": "kicanvas",
#                 "path": "https://raw.githubusercontent.com/opulo-inc/lumenpnp/main/pnp/pcb/ring-light/ringLight.kicad_pcb"
#             }
#         }
# </script>