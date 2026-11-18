"""Tests for the crate kit that do not need Blender: the layout maths, the arguments and the manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import crate

ROOT = Path(__file__).resolve().parents[1]


def test_toggle_words_from_the_studio_are_understood():
    for yes in ("True", "true", "1", "yes"):
        assert crate.as_bool(yes) is True
    for no in ("False", "false", "0", "no"):
        assert crate.as_bool(no) is False
    with pytest.raises(ValueError):
        crate.as_bool("maybe")


def test_parse_args_defaults_and_flags():
    args = crate.parse_args(["crate.py", "--", "out/run", "--kind", "chest", "--bands", "True"])
    assert args.out == Path("out/run")
    assert args.kind == "chest" and args.bands is True
    assert (args.width, args.depth, args.height) == (1.0, 1.0, 1.0)
    assert args.model is None and args.label is None


def test_unknown_shape_is_refused():
    with pytest.raises(SystemExit):
        crate.parse_args(["crate.py", "--", "out", "--kind", "coffin"])


def test_plank_rows_fill_the_height_with_a_small_gap():
    n, plank, gap = crate.plank_rows(1.0)
    assert n == 8
    assert n * plank + (n - 1) * gap == pytest.approx(1.0)
    assert gap < plank / 4
    assert crate.plank_rows(0.2)[0] >= 2


def test_fit_dimensions_add_room_on_every_side():
    w, d, h = crate.fit_dimensions((-0.5, -0.25, 0.0), (0.5, 0.25, 1.8), padding=0.1)
    assert (w, d, h) == pytest.approx((1.2, 0.7, 2.0))
    assert crate.fit_dimensions((0, 0, 0), (1, 1, 1), padding=0) == (1, 1, 1)
    with pytest.raises(ValueError):
        crate.fit_dimensions((0, 0, 0), (0, 1, 1), padding=0.1)


def test_every_shape_plans_parts_that_stay_inside_the_size_asked_for():
    for kind in crate.KINDS:
        for bands in (False, True):
            parts = crate.plan(kind, 1.0, 0.8, 1.2, bands=bands)
            assert parts, kind
            for p in parts:
                for axis, limit in enumerate((1.0, 0.8, 1.2)):
                    half = p.size[axis] / 2
                    if axis == 2:
                        assert -1e-6 <= p.location[2] - half <= limit, (kind, p)
                        assert p.location[2] + half <= limit + 0.06, (kind, p)
                    else:
                        assert abs(p.location[axis]) + half <= limit / 2 + 0.03, (kind, p)


def test_bands_add_metal_parts_and_only_when_asked():
    plain = crate.plan("crate", 1, 1, 1, bands=False)
    banded = crate.plan("crate", 1, 1, 1, bands=True)
    assert not any(p.material == "metal" for p in plain)
    assert any(p.material == "metal" for p in banded)
    assert len(banded) > len(plain)


def test_a_label_is_one_flat_part_on_the_front_face():
    parts = crate.plan("crate", 1.0, 0.6, 1.0, bands=False, label=True)
    labels = [p for p in parts if p.material == "label"]
    assert len(labels) == 1
    assert labels[0].location[1] < -0.3          # on the front, outside the planks
    assert crate.plan("crate", 1, 1, 1, label=False) == [p for p in crate.plan("crate", 1, 1, 1) if p.material != "label"]


def test_size_checks():
    for bad in ((0, 1, 1), (1, -1, 1), (1, 1, 0)):
        with pytest.raises(ValueError):
            crate.plan("crate", *bad)
    with pytest.raises(ValueError):
        crate.plan("coffin", 1, 1, 1)


def test_the_manifest_matches_the_script():
    manifest = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == 1 and manifest["id"] == "crate-kit"
    ids = [t["id"] for t in manifest["tools"]]
    assert ids == ["build", "fit", "label"]
    types = {i["type"] for t in manifest["tools"] for i in t["inputs"]}
    assert {"choice", "number", "toggle", "model", "picture"} <= types
    for tool in manifest["tools"]:
        assert tool["makes"] == "glb"
        assert "crate.py" in tool["run"]
        flags = [a for a in tool["run"] if a.startswith("--") and a != "--"]   # a bare "--" is Blender's own separator
        # every flag the manifest passes is one the script accepts, and every placeholder is a declared input
        accepted = set(crate.build_parser()._option_string_actions)
        assert set(flags) <= accepted, tool["id"]
        declared = {i["id"] for i in tool["inputs"]}
        used = {a[1:-1] for a in tool["run"] if a.startswith("{") and a.endswith("}")} - {"out", "blender"}
        assert used == declared, tool["id"]
