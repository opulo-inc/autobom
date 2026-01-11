# AutoBOM

AutoBOM is a Bill of Materials exporting and rendering tool. It does:

- Automatic exporting of manufacturing filetypes for 3D models, circuit boards, and wire harnesses
- Generating a shareable Bill of Materials webpage with renders of all parts
- Standardization of a Bill of Materials format

AutoBOM is a command line tool and can be run locally, but is meant to be used as a Github Action for automatic exporting and rendering of a BoM for hardware releases.

It is an effort to formalize and standardize the smattering of automatic export and render tools developed as part of the [LumenPnP project](https://github.com/opulo-inc/lumenpnp).

This is still *heavily* in beta. There are bugs abound. Very likely any bug reports will become pretty out of date pretty quickly at this stage, but feature requests are welcome!

There are only a handful of CAD packages that we can support, given that all this exporting needs to run headless and automatically. Here is the list of planned packages we will support:

- [x] FreeCAD
- [ ] OpenSCAD
- [x] KiCAD
- [ ] Wireviz

## Usage

### Running in Github Actions

Autobom is designed to be run automatically using Github Actions. It's simple to set up your hardware repository to work with Autobom. You just need three things:

1. An `autobom.json` file in the root of your repository. This contains settings about how to perform the export.
2. A bill of materials! This can be named and placed wherever you'd like, as the name is specified in `autobom.json`. It must conform to the expected format. All items in the BOM must have their soruce files *somewhere* in the repository. It will hunt for the correct files based on the cad type and part name, but you can be more explicit if you'd like.
3. Add the `autobom.yaml` file to your repo in the `.github/workflows` folder.

That's it! Now, when you publish a release or request Autobom to run as a workflow dispatch, it'll generate the zipped export of your source and upload it as an Artifact.

### Running local

This assumes this is being run on Apple ARM silicon.

1. Get render engines running. From autobom repo root, run:
  
    `docker-compose -f docker-compose-local.yaml up -d`

2. Run Autobom. `cd` to the project repo root, and run:

    `uv run --project /path/to/autobom/repo autobom`

3. You'll get a shiny new `autobom` folder in the root of the project repo with all the exported files.

## References and Dependencies

- [KiCanvas](https://kicanvas.org/)
- [Online3DViewer](https://github.com/kovacsv/Online3DViewer)
- [FreeCAD](https://github.com/FreeCAD/FreeCAD)
- [KiCAD](https://gitlab.com/kicad/code/kicad)
- [KiBot](https://github.com/INTI-CMNB/KiBot)
- [OpenSCAD](https://github.com/openscad/openscad/)

## DEV

Here's a rough breakdown of what's in this repo

- `./render` contains scripts, Dockerfiles, and other assets used for spinning up the render engines. These are the docker containers whose sole purpose is to do the actual work of exporting files from various CAD packages.
  - `Dockerfile-freecad-gha` defines the container for the freecad "render engine" when running in Github Actions, a standalone container that runs freecad (and openscad) whos sole purpose is to process openscad and freecad source files and export their stls, steps, and rendered images. it depends on there being a `/renderQueue` directory mounted. Note that there's also a `Dockerfile-freecad-local` meant to be used when testing on Apple Silicon.
  - `Dockerfile-kicad` is the same as above, but with kicad! instead of dropping individual files into `/renderQueue/kicad/in`, instead drop in a whole project directory.
  - `./docker-compose-local.yaml` is a docker compose file meant to be run on a Mac with Apple ARM silicon. It just chooses a different Freecad Dockerfile because of some archtecture nightmares.
  - `./docker-compose.yaml` is the main docker compose file meant to be run in the Github Action. It uses the `x86_64` FreeCAD Dockerfile.
- `./renderQueue` is a folder that the "render engine" docker containers use to find parts to export, and a place for them to drop the exported assets.
- `./src` is where all the Autobom python source exists. This is what generates the website, parses the bom and config files, finds the source files, and makes decisions about what files get rendered where.
- `./action.yaml` is the file Github looks for when folks call our action! This is the heart of the whole thing, the file that decides what gets run on Github's server.


TODO:
- render engines need to be robust to stuff failing, currently just dies if it doesnt find a body named "Body" in freecad file, for instance.
- kicad exported files arent deleted from `kicad/out` after copied to the export folder, this fails in the CI for some reason
- openscad has not been fully tested in CI
- logging is messy
- generally needs a refactor, chunks of logic have moved around with reckless abandon, now that things are a bit more stable the general structure of the autobom python codebase needs a refresh

helpful:
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/accessing-contextual-information-about-workflow-runs#github-context
- https://docs.github.com/en/actions/sharing-automations/creating-actions/metadata-syntax-for-github-actions
- https://docs.github.com/en/actions/sharing-automations/creating-actions/creating-a-docker-container-action