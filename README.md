# AutoBOM

AutoBOM is a Bill of Materials exporting and rendering tool. It does:

- Automatic exporting of manufacturing filetypes for 3D models, circuit boards, and wire harnesses
- Generating a shareable Bill of Materials webpage with renders of all parts
- Standardization of a Bill of Materials format

AutoBOM is a command line tool and can be run locally, but is meant to be used as a Github Action for automatic exporting and rendering of a BoM for hardware releases.

It is an effort to formalize and standardize the smattering of automatic export and render tools developed as part of the [LumenPnP project](https://github.com/opulo-inc/lumenpnp).

This is still *heavily* in beta. There are bugs abound. Please report any issues by making a Github Issue.

There are only a handful of CAD packages that we can support, given that all this exporting needs to run headless and automatically. Here is the list of planned packages we will support:

- [x] FreeCAD
- [x] OpenSCAD
- [x] KiCAD
- [ ] Wireviz

## Usage

You can try running autobom within this repository! Autobom needs three things to run:

1. An `autobom.json` file in the directory where it's run. This contains settings about how to perform the export and render.
2. A bill of materials! This can be named whatever you'd like, as the name is specified in `autobom.json`. It must conform to the expected format.
3. The source files *somewhere* in the directory where autobom is run. It will hunt for the correct files based on the cad type and part name, but you can be more explicit if you'd like.

That's it! After running it, you'll have a newly generated folder with a webpage showing you all the parts in your BoM, and all the exported files ready for production.

## References and Dependencies

- [KiCanvas](https://kicanvas.org/)
- [Online3DViewer](https://github.com/kovacsv/Online3DViewer)
- [FreeCAD](https://github.com/FreeCAD/FreeCAD)
- [KiCAD](https://gitlab.com/kicad/code/kicad)
- [KiBot](https://github.com/INTI-CMNB/KiBot)
- [OpenSCAD](https://github.com/openscad/openscad/)

## DEV

ok so right now this is kind of a mess. here's a breakdown of what's what:

- `./example` is a fake project that is used for testing autobom. it has a bom.json (used for listing parts), autobom.json (used for config), and some source.
- `./renderQueue` is a folder that the "render engine" docker containers use to find parts to export, and a place for them to drop the exported assets
- `./src` is where all the autobom python source is hangin out. the exception (very messy, should be moved elsewhere) is `./src/autobom/render` has standalone python scripts and bash script entrypoints for the render engine docker containers to run on boot.
- `./` has a ton of docker stuff, which should honestly be all put into it's own folder with the `./src/autobom/render` stuff too:
  - `Dockerfile-freecad` defines the container for the freecad "render engine," a standalone container that runs freecad (and openscad) whos sole purpose is to process openscad and freecad source files and export their stls, steps, and rendered images. it depends on there being a `/renderQueue` directory mounted.
  - `Dockerfile-kicad` is the same as above, but with kicad! instead of dropping individual files into `/renderQueue/kicad/in`, instead drop in a whole project directory
  - `Dockerfile` is an attempt at making a container that actually runs autobom. might not be needed? not sure.
  - `docker-compose.yaml` is a compose file that currently spins up both render engines at the same time, and binds them to the `./renderQueue` directory, so it's easy to drop files in for testing. it currently does not run autobom.

outstanding stuff:
- autobom (the python project) still needs to copy source files into the renderQueue directory, and copy the resulting exported files into the final autobom artifact. and intelligently handle failure, add to autobom manifest, or quit?
- how does all this connect? in docker-compose.yaml, do we have a third container that runs autobom? how do we pass it the repository path? and how does this run either 1) on the command line, or 2) in a composite github action? current thought is passing the path to the repo to process in as an environment variable.
- render engines need to be robust to stuff failing, currently just dies if it doesnt find a body named "Body" in freecad file, for instance.
- restructure so it's not a mess