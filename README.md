# Crate kit

An AssetFurnace add-on that makes crates, barrels and chests. It was built to show how an add-on
hooks into the app, so every part of it is small and meant to be read.

## What it does

Three tools:

- **Build a crate**: pick a shape (crate, barrel, chest), a size, and whether it has metal bands.
- **Fit a crate around a model**: pick a model you already made and get a crate just big enough to hold it.
  The new file keeps the model's licence record.
- **Build a crate with a label**: put your own picture on the front.

Each tool writes one GLB, with a `.provenance.json` next to it.

## Install

To try a copy that is not on the list yet:

```bash
./lab addon add --unlisted https://github.com/AssetFurnace/crate-addon.git@<commit-hash>
```

Needs Blender 4.2 or newer. Nothing is downloaded.

## Use

From the studio's Add-ons page, or the command line:

```bash
./lab addon run crate-kit build --input kind=chest --input width=1 --input depth=0.6 --input height=0.8 --input bands=true --yes
./lab addon run crate-kit fit --input model=output/my-prop.glb --input padding=0.1 --input kind=crate --yes
./lab addon run crate-kit label --input label=logo.png --input width=1 --input height=1 --yes
```

## How it is built

- `addon.json` declares the tools and their inputs. The studio draws the forms from it.
- `crate.py` does the work. The layout maths (`plan`, `plank_rows`, `fit_dimensions`) is plain Python with
  tests; only `build_scene` and `export_glb` need Blender.
- `tests/` runs without Blender: `python3 -m pytest -q tests`.

## Licence

Apache-2.0
