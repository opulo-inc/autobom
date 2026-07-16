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

1. In your hardware repo root, add `autobom.json` and a BOM file (see [Config](#config) below).
2. Copy [`examples/autobom.workflow.yaml`](examples/autobom.workflow.yaml) to `.github/workflows/autobom.yaml` (or paste the snippet below).
3. Ensure render images are published for the tag you pin (see [Publish images](#publish-images)). On first use after a release, run the **Publish render engine images** workflow in this repo if needed.
4. Push a release or run the workflow via **workflow_dispatch**. AutoBOM uploads an `Autobom` artifact containing exports, renders, `index.html`, and `manifest.json`.

```yaml
name: AutoBOM

on:
  release:
    types: [published]
  workflow_dispatch:

jobs:
  autobom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: opulo-inc/autobom@v0.2.0
        with:
          image-tag: latest
```

Pin a release tag (`@v0.2.0`) rather than `@main` for reproducible builds.

### Config

**`autobom.json`** (repo root):

```json
{
  "source_url": "https://github.com/org/your-hardware-repo",
  "bom_path": "bom.json",
  "mcad": {
    "export": "step",
    "render": "src",
    "path": "mcad"
  },
  "ecad": {
    "export": "gerber",
    "render": "src",
    "path": "ecad"
  },
  "site": {
    "colors": {
      "primary": "daa520",
      "secondary": "af8000"
    }
  }
}
```

**`bom.json`** (path from `bom_path`):

```json
{
  "name": "MyProduct",
  "version": "v1.0.0",
  "parts": [
    {
      "name": "my-bracket",
      "quantity": 2,
      "type": "mcad",
      "optional": false,
      "source": "https://example.com",
      "notes": ""
    },
    {
      "name": "main-board",
      "quantity": 1,
      "type": "ecad",
      "optional": false,
      "source": "https://example.com",
      "notes": ""
    }
  ]
}
```

- `type`: `mcad` (FreeCAD `.FCStd` / OpenSCAD `.scad`) or `ecad` (KiCAD `.kicad_pro`)
- `name` must match the source filename / KiCAD project name
- `optional: true` skips failing that part without failing the whole job
- CAD sources are searched under `mcad.path` / `ecad.path` if set, otherwise the whole repo

See also [opulo-inc/example-autobom-project](https://github.com/opulo-inc/example-autobom-project).

### Running local

This assumes this is being run on Apple ARM silicon.

1. Get render engines running. From autobom repo root, run:
  
    `docker compose -f docker-compose-local.yaml up -d --build`

2. Run Autobom. `cd` to the project repo root, and run:

    `uv run --project /path/to/autobom/repo autobom`

3. You'll get a shiny new `autobom` folder in the root of the project repo with all the exported files.

To export STEP from every FreeCAD file in a tree:

    `uv run --project /path/to/autobom/repo export-freecad`

### Publish images

GitHub Actions uses prebuilt images:

- `ghcr.io/opulo-inc/autobom-freecad`
- `ghcr.io/opulo-inc/autobom-kicad`

They are built by [`.github/workflows/publish-images.yml`](.github/workflows/publish-images.yml) on pushes to `main`, version tags, or manual `workflow_dispatch`. Packages must be public (or the consumer workflow must authenticate to GHCR) for `docker pull` to work in other repos.

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
  - `Dockerfile-freecad-gha` defines the container for the freecad "render engine" when running in Github Actions (x86_64 FreeCAD AppImage).
  - `Dockerfile-freecad-local` is for Apple Silicon local testing.
  - `Dockerfile-kicad` runs KiBot against a whole KiCAD project directory.
  - `./docker-compose-local.yaml` builds images locally for Mac ARM.
  - `./docker-compose.yaml` pulls GHCR images for the Github Action.
- `./renderQueue` is a folder that the render engine docker containers use to exchange source/export files with the host.
- `./src` is where all the Autobom python source exists. This is what generates the website, parses the bom and config files, finds the source files, and makes decisions about what files get rendered where.
- `./action.yaml` is the composite Github Action entrypoint.
- Builder ↔ renderers talk over TCP (JSON length-prefixed messages) on ports 9001 (MCAD) and 9002 (ECAD).

TODO:
- openscad has not been fully tested in CI
- logging is messy
- generally needs a refactor, chunks of logic have moved around with reckless abandon, now that things are a bit more stable the general structure of the autobom python codebase needs a refresh
