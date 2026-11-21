# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

"""
Loads autobom.json and resolves it into one config per BOM to build.

Top-level keys are defaults. An optional "boms" array lists several BOMs, each
with its own bom_path and optional overrides of the top-level keys.
"""

import copy, json, os, re

OUTPUT_DIR = "autobom"

# Sections merged one level deep (per-BOM keys override, the rest are inherited).
MERGED_SECTIONS = ("mcad", "ecad", "wcad", "site")

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ConfigError(Exception):
    pass


def load_config(repo_path):
    path = os.path.join(repo_path, "autobom.json")
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"No autobom.json found at {path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"autobom.json is not valid JSON: {e}")


def _merge_section(name, base, override):
    if not isinstance(override, dict):
        raise ConfigError(f"'{name}' must be an object")
    merged = {**(base or {}), **override}
    if name == "site" and isinstance(override.get("colors"), dict):
        merged["colors"] = {**(base or {}).get("colors", {}), **override["colors"]}
    return merged


def _merge(defaults, entry):
    merged = copy.deepcopy(defaults)
    for key, value in entry.items():
        if key == "id":
            continue
        if key in MERGED_SECTIONS:
            merged[key] = _merge_section(key, defaults.get(key), value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def resolve_boms(config):
    """Return a list of (bom_id, merged_config, out_dir).

    Without a "boms" array this is a single build into autobom/ (bom_id is None).
    """
    if "boms" not in config:
        if "bom_path" not in config:
            raise ConfigError("autobom.json needs either 'bom_path' or a 'boms' array")
        return [(None, config, OUTPUT_DIR)]

    if "bom_path" in config:
        raise ConfigError(
            "autobom.json has both 'bom_path' and 'boms'; use one or the other "
            "(put bom_path inside each 'boms' entry)"
        )

    boms = config["boms"]
    if not isinstance(boms, list) or not boms:
        raise ConfigError("'boms' must be a non-empty array")

    defaults = {k: v for k, v in config.items() if k != "boms"}
    resolved = []
    seen = set()
    for i, entry in enumerate(boms):
        if not isinstance(entry, dict):
            raise ConfigError(f"boms[{i}] must be an object")
        bom_id = entry.get("id")
        if not bom_id:
            raise ConfigError(f"boms[{i}] is missing 'id'")
        if not isinstance(bom_id, str) or not _ID_PATTERN.match(bom_id):
            raise ConfigError(
                f"boms[{i}] id {bom_id!r} must be a slug (letters, digits, '.', '_', '-')"
            )
        if bom_id in seen:
            raise ConfigError(f"Duplicate BOM id {bom_id!r} in 'boms'")
        seen.add(bom_id)
        if not entry.get("bom_path"):
            raise ConfigError(f"BOM {bom_id!r} is missing 'bom_path'")

        resolved.append((bom_id, _merge(defaults, entry), os.path.join(OUTPUT_DIR, bom_id)))
    return resolved
