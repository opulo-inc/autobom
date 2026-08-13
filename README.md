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
3. Push a release or run the workflow via **workflow_dispatch**. AutoBOM uploads an `Autobom` artifact containing exports, renders, `index.html`, and `manifest.json`.

Each Action run builds the FreeCAD and KiCAD Docker images from the Dockerfiles in this repo (slow the first time / when Dockerfiles change; simple and self-contained).

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
```

Pin a release tag (`@v0.2.0`) rather than `@main` for reproducible builds.

### Config

Place **`autobom.json`** in the root of your hardware repository. AutoBOM reads this file first, then loads the BOM at `bom_path`.

#### `autobom.json` reference

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

| Key | Required | Description |
|-----|----------|-------------|
| `source_url` | **yes** | Base URL of the hardware repo (no trailing slash). Used in the generated BOM page header and to build GitHub `blob/<sha>/…` links when `render` is `"src"`. |
| `bom_path` | **yes** | Path to the BOM JSON file, relative to the hardware repo root (e.g. `"bom.json"` or `"docs/bom.json"`). |
| `mcad` | **yes** | Defaults for mechanical CAD parts (`type: "mcad"` in the BOM). See below. |
| `ecad` | **yes** | Defaults for electronics CAD parts (`type: "ecad"` in the BOM). See below. |
| `site` | **yes** | Options for the generated BOM webpage. See below. |
| `strict` | no | Default `false`. If `true`, the job exits non-zero when any non-`optional` part is missing or fails to export. If `false` (default), those are logged as warnings and the `autobom/` output is still produced. |

##### `mcad`

Controls mechanical parts (FreeCAD `.FCStd`, OpenSCAD `.scad`).

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `export` | **yes** | — | Which manufacturing export to record in `manifest.json` for each mcad part. Allowed: `"step"`, `"stl"`. (The FreeCAD render engine still runs the full export/render pass; this field selects which file path is written into the part’s `export` entry in the manifest.) |
| `render` | **yes** | — | How the BOM page should prefer to display this part. See [Render modes](#render-modes) below. |
| `path` | no | *(whole repo)* | Subdirectory (relative to repo root) to search for source files. If omitted, AutoBOM walks the entire repository. Example: `"pnp/cad"`. |

##### `ecad`

Controls electronics parts (KiCAD projects with a `.kicad_pro` file).

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `export` | **yes** | — | Intended manufacturing export mode. Conventional value: `"gerber"`. Today KiBot always runs the outputs defined in AutoBOM’s `render/config.kibot.yaml` (gerbers, plots, BOM CSV, etc.) regardless of this string; keep `"gerber"` for forward compatibility. |
| `render` | **yes** | — | How the BOM page should prefer to display this part. See [Render modes](#render-modes) below. |
| `path` | no | *(whole repo)* | Subdirectory (relative to repo root) to search for KiCAD projects. If omitted, AutoBOM walks the entire repository. Example: `"pnp/pcb"`. |

##### `site`

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `colors` | no | see below | Theme colors for the generated BOM page. Hex values **without** a leading `#`. |
| `colors.primary` | no | `"daa520"` | Primary accent color. |
| `colors.secondary` | no | `"af8000"` | Secondary accent color. |

`site` itself must be present (even as `{}`). Color keys are accepted and merged with defaults; full CSS theming from these values is still evolving.

##### Render modes

Used by both `mcad.render` and `ecad.render` (and by per-part overrides in the BOM):

| Value | Behavior |
|-------|----------|
| `"src"` | Prefer an interactive source viewer. For mcad, builds a GitHub link to the FreeCAD/OpenSCAD file at the build commit (`source_url` + `/blob/<sha>/…`) for Online3DViewer. For ecad, points at the project path similarly; preview PNGs from the export pass are also recorded. |
| `"img"` | Prefer a static preview image from the export output (`export/<name>.png` for mcad, `export/<name>/<name>-top.png` for ecad). |
| *(any other string)* | Treated as a custom image URL/path and used as the part’s `img_path` (useful for hosting a pre-rendered preview elsewhere). |

Any part in `bom.json` may set its own `"render"` or `"export"` field to override the matching `mcad` / `ecad` default for that part only.

---

#### `bom.json` (path from `bom_path`)

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
      "notes": "",
      "render": "img",
      "export": "gerber"
    }
  ]
}
```

| Key | Required | Description |
|-----|----------|-------------|
| `name` | **yes** | Product name shown on the BOM page and in `manifest.json`. |
| `version` | **yes** | Product/version string shown on the BOM page (e.g. `"v1.0.0"` or `"main"`). |
| `parts` | **yes** | Array of part objects (see below). |

##### Part object

| Key | Required | Description |
|-----|----------|-------------|
| `name` | **yes** | Must match the FreeCAD/OpenSCAD filename stem (e.g. `my-bracket` → `my-bracket.FCStd`) or the KiCAD project name (directory containing `my-bracket.kicad_pro`). |
| `quantity` | **yes** | Count shown in the BOM table. |
| `type` | **yes** | `"mcad"` (FreeCAD / OpenSCAD), `"ecad"` (KiCAD). `"wcad"` and `"misc"` are recognized but not processed yet. |
| `optional` | no | Default `false`. If `true`, a missing source or failed export/render does **not** fail the overall job. |
| `source` | no | Link shown in the BOM table (vendor page, datasheet, repo path, etc.). |
| `notes` | no | Free-text note shown in the BOM table. |
| `render` | no | Overrides `mcad.render` / `ecad.render` for this part only. Same values as [Render modes](#render-modes). |
| `export` | no | Overrides `mcad.export` / `ecad.export` for this part only. |

CAD sources are searched under `mcad.path` / `ecad.path` when set; otherwise the whole repo.

See also [opulo-inc/example-autobom-project](https://github.com/opulo-inc/example-autobom-project).

### Running local

Requires Docker Desktop (or equivalent) running. From your hardware repo root:

```bash
uv run --project /path/to/autobom/repo autobom
```

Locally, `autobom` starts the FreeCAD/KiCAD containers if they aren’t already up, waits for ports 9001/9002, runs the build, then stops containers it started. On Apple Silicon it uses `docker-compose-local.yaml`; elsewhere `docker-compose.yaml`.

- If engines are already running, they are reused and left up afterward.
- To keep engines you started (faster re-runs): `AUTOBOM_KEEP_ENGINES=1 uv run --project /path/to/autobom/repo autobom`

Under GitHub Actions, `action.yaml` owns container start/stop; the CLI does not manage Docker there.

You'll get an `autobom/` folder in the hardware repo root with exports and `index.html`.

To export STEP from every FreeCAD file in a tree:

    `uv run --project /path/to/autobom/repo export-freecad`

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
  - `./docker-compose.yaml` builds images for the Github Action (x86 FreeCAD + KiCAD).
- `./renderQueue` is a folder that the render engine docker containers use to exchange source/export files with the host.
- `./src` is where all the Autobom python source exists. This is what generates the website, parses the bom and config files, finds the source files, and makes decisions about what files get rendered where.
- `./action.yaml` is the composite Github Action entrypoint.
- Builder ↔ renderers talk over TCP (JSON length-prefixed messages) on ports 9001 (MCAD) and 9002 (ECAD).

TODO:
- openscad has not been fully tested in CI
- logging is messy
- generally needs a refactor, chunks of logic have moved around with reckless abandon, now that things are a bit more stable the general structure of the autobom python codebase needs a refresh
