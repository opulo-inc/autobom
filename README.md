# AutoBOM

AutoBOM is a Bill of Materials exporting and rendering tool. It does:

- Automatic exporting of manufacturing filetypes for 3D models, circuit boards, and wire harnesses
- Generating a shareable Bill of Materials webpage with renders of all parts
- Standardization of a Bill of Materials format

AutoBOM is a command line tool and can be run locally, but is meant to be used as a Github Action for automatic exporting and rendering of a BoM for hardware releases.

## Status

This is still *heavily* in beta. There are bugs abound. Please report any issues by making a Github Issue.

There are only a handful of CAD packages that we can support, given that all this exporting needs to run headless and automatically. Here is the list of planned packages we will support:

- [x] FreeCAD
- [ ] OpenSCAD
- [ ] KiCAD
- [ ] Wireviz

## Install

With Hatch installed, from the autobom directory, run:

```console
    hatch env create
```

Then, if you want to test building and running as a command line tool:

```console
    hatch build
    pip install .
    autobom
```

Or, to just run within hatch:

```console
    hatch run autobom
```

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
