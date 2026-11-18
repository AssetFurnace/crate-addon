#!/usr/bin/env python3
"""Build a crate, barrel or chest and export it as a GLB.

Run inside Blender:

    blender -b -P crate.py -- <out-dir> --kind crate --width 1 --depth 1 --height 1 --bands true
    blender -b -P crate.py -- <out-dir> --kind chest --model prop.glb --padding 0.1
    blender -b -P crate.py -- <out-dir> --kind crate --label label.png

The result is written to `<out-dir>/<out-dir-name>.glb`.

The layout is plain maths (`plan`, `plank_rows`, `fit_dimensions`) so it is tested without Blender.
Only `build_scene` and `export_glb` touch Blender.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

KINDS = ("crate", "barrel", "chest")
PLANK_TARGET = 0.12      # metres: how tall one plank is meant to be
POST = 0.07              # corner post thickness
SKIN = 0.012             # how far bands and labels stand off the wood
COLOURS = {"wood": (0.55, 0.36, 0.19), "dark_wood": (0.34, 0.21, 0.11), "metal": (0.32, 0.32, 0.35)}


@dataclass(frozen=True)
class Part:
    """One piece of the model: a box or an upright cylinder, centred at `location` (z is up, base of the model at 0)."""
    shape: str                       # "box" or "cylinder"
    size: tuple[float, float, float]  # box: x, y, z. cylinder: diameter, diameter, height
    location: tuple[float, float, float]
    material: str                    # "wood", "dark_wood", "metal" or "label"


def as_bool(text: str) -> bool:
    """The studio hands a toggle over as a word; accept the usual ones."""
    word = str(text).strip().lower()
    if word in ("true", "1", "yes"):
        return True
    if word in ("false", "0", "no"):
        return False
    raise ValueError(f"expected true or false, got {text!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a crate, barrel or chest")
    parser.add_argument("out", type=Path, help="output directory")
    parser.add_argument("--kind", choices=KINDS, default="crate")
    parser.add_argument("--width", type=float, default=1.0, help="metres, left to right")
    parser.add_argument("--depth", type=float, default=1.0, help="metres, front to back")
    parser.add_argument("--height", type=float, default=1.0, help="metres")
    parser.add_argument("--bands", type=as_bool, default=False, help="metal bands: true or false")
    parser.add_argument("--model", type=Path, default=None, help="size the crate to hold this GLB")
    parser.add_argument("--padding", type=float, default=0.05, help="spare room around --model, metres")
    parser.add_argument("--label", type=Path, default=None, help="a picture for the front")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the arguments after the `--` that separates them from Blender's own."""
    argv = argv if argv is not None else sys.argv
    own = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return build_parser().parse_args(own)


def plank_rows(height: float) -> tuple[int, float, float]:
    """How many planks fit the height, how tall each is, and the gap between them."""
    n = max(2, round(height / PLANK_TARGET))
    gap = (height / n) * 0.12
    plank = (height - (n - 1) * gap) / n
    return n, plank, gap


def fit_dimensions(bmin, bmax, padding: float) -> tuple[float, float, float]:
    """Inside size of a crate that holds a box from `bmin` to `bmax`, with `padding` of spare room each side."""
    if padding < 0:
        raise ValueError("padding cannot be negative")
    size = [hi - lo for lo, hi in zip(bmin, bmax)]
    if min(size) <= 0:
        raise ValueError("the model has no size to fit")
    return (size[0] + 2 * padding, size[1] + 2 * padding, size[2] + 2 * padding)


def _box_crate(w, d, h, bands, label):
    parts = [Part("box", (w, d, 0.03), (0, 0, 0.015), "dark_wood")]            # floor
    n, plank, gap = plank_rows(h)
    for i in range(n):
        z = i * (plank + gap) + plank / 2
        # front and back run the full width, left and right fit between them
        for y in (-d / 2 + 0.015, d / 2 - 0.015):
            parts.append(Part("box", (w, 0.03, plank), (0, y, z), "wood"))
        for x in (-w / 2 + 0.015, w / 2 - 0.015):
            parts.append(Part("box", (0.03, d - 0.06, plank), (x, 0, z), "wood"))
    for sx in (-1, 1):                                                          # corner posts
        for sy in (-1, 1):
            parts.append(Part("box", (POST, POST, h), (sx * (w / 2 - POST / 2), sy * (d / 2 - POST / 2), h / 2), "dark_wood"))
    if bands:
        for z in (h * 0.18, h * 0.82):
            parts += _ring_bands(w, d, z)
    if label:
        side = min(w, h) * 0.5
        parts.append(Part("box", (side, 0.002, side), (0, -d / 2 - SKIN, h / 2), "label"))
    return parts


def _ring_bands(w, d, z, thick=0.025, tall=0.05):
    off = SKIN
    return [
        Part("box", (w + 2 * off, thick, tall), (0, -d / 2 - off + thick / 2, z), "metal"),
        Part("box", (w + 2 * off, thick, tall), (0, d / 2 + off - thick / 2, z), "metal"),
        Part("box", (thick, d + 2 * off, tall), (-w / 2 - off + thick / 2, 0, z), "metal"),
        Part("box", (thick, d + 2 * off, tall), (w / 2 + off - thick / 2, 0, z), "metal"),
    ]


def _barrel(w, d, h, bands):
    diameter = min(w, d)
    parts = [Part("cylinder", (diameter, diameter, h), (0, 0, h / 2), "wood")]
    rings = (0.15, 0.4, 0.6, 0.85) if bands else (0.12, 0.88)
    for f in rings:
        parts.append(Part("cylinder", (diameter + 2 * SKIN, diameter + 2 * SKIN, 0.045), (0, 0, h * f), "metal"))
    return parts


def _chest(w, d, h, bands):
    body_h = h * 0.65
    parts = _box_crate(w, d, body_h, bands=False, label=False)
    parts.append(Part("box", (w + 0.02, d + 0.02, h - body_h), (0, 0, body_h + (h - body_h) / 2), "dark_wood"))   # lid
    if bands:
        parts += _ring_bands(w, d, body_h * 0.5) + _ring_bands(w, d, body_h + (h - body_h) / 2)
    return parts


def plan(kind: str, width: float, depth: float, height: float, bands: bool = False, label: bool = False) -> list[Part]:
    """Every part of the model, as plain data. A barrel is as wide as the smaller of width and depth."""
    if kind not in KINDS:
        raise ValueError(f"unknown shape: {kind}")
    if min(width, depth, height) <= 0:
        raise ValueError("width, depth and height must be positive")
    if kind == "barrel":
        return _barrel(width, depth, height, bands)
    if kind == "chest":
        return _chest(width, depth, height, bands)
    return _box_crate(width, depth, height, bands, label)


# ---- everything below needs Blender ---------------------------------------------------------

def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablock in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(datablock):
            datablock.remove(item)


def model_bounds(path: Path):
    """Import a GLB, measure it, and remove it again. Returns (min, max) corners in Blender's z-up space."""
    import bpy
    from mathutils import Vector

    bpy.ops.import_scene.gltf(filepath=str(path))
    corners = [obj.matrix_world @ Vector(c) for obj in bpy.context.scene.objects if obj.type == "MESH" for c in obj.bound_box]
    if not corners:
        raise ValueError("that model has no mesh to fit")
    lo = tuple(min(c[i] for c in corners) for i in range(3))
    hi = tuple(max(c[i] for c in corners) for i in range(3))
    clear_scene()
    return lo, hi


def _material(name: str, label: Path | None):
    import bpy

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    if name == "label":
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(label))
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        r, g, b = COLOURS[name]
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.4 if name == "metal" else 0.85
        bsdf.inputs["Metallic"].default_value = 0.9 if name == "metal" else 0.0
    return mat


def build_scene(parts: list[Part], label: Path | None = None) -> None:
    import bpy

    materials = {}
    for i, part in enumerate(parts):
        if part.shape == "box":
            bpy.ops.mesh.primitive_cube_add(size=1, location=part.location)
            bpy.context.active_object.scale = part.size
        else:
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.5, depth=1, location=part.location)
            bpy.context.active_object.scale = part.size
        obj = bpy.context.active_object
        obj.name = f"{part.material}_{i}"
        if part.material not in materials:
            materials[part.material] = _material(part.material, label)
        obj.data.materials.append(materials[part.material])
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def export_glb(out_dir: Path) -> Path:
    """Export the scene as a GLB named after the output folder."""
    import bpy

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{out_dir.name}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_apply=True)
    return path


def main(argv: list[str] | None = None) -> Path:
    args = parse_args(argv)
    clear_scene()
    width, depth, height = args.width, args.depth, args.height
    if args.model is not None:
        width, depth, height = fit_dimensions(*model_bounds(args.model), args.padding)
    build_scene(plan(args.kind, width, depth, height, bands=args.bands, label=args.label is not None), args.label)
    return export_glb(args.out)


if __name__ == "__main__":
    main()
