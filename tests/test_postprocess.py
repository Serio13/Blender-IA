import sys
from pathlib import Path

import bpy
import numpy as np
import pytest

from pirate_prop_forge.core import meshutil, postprocess
from pirate_prop_forge.core.errors import PFError

WORKER = Path(__file__).resolve().parents[1] / "addon" / "pirate_prop_forge" / "worker"


def fake_obj(tmp_path):
    sys.path.insert(0, str(WORKER))
    try:
        from backends import fake
    finally:
        sys.path.remove(str(WORKER))
    out = tmp_path / "raw.obj"
    fake.Backend().generate("x", str(out), {}, lambda *a: None, lambda: False)
    return out


def opts(**kw):
    kw.setdefault("material", "none")
    return postprocess.Options(**kw)


def test_import_fixes_axes(tmp_path):
    obj = postprocess.import_mesh(fake_obj(tmp_path))
    pts = meshutil.world_points(obj)
    assert pts[:, 2].max() == pytest.approx(350, abs=1) and pts[:, 2].min() < 10   # Z es la altura
    assert pts[:, 0].max() > 800                                  # el fragmento flotante esta lejos en X


def test_process_cleans_scales_and_places(tmp_path):
    obj, rep = postprocess.process(fake_obj(tmp_path), "Barril_ia_V2", opts(category="barril"))
    assert obj.name == "Barril_ia_V2_malla_BAKED"
    pts = meshutil.world_points(obj)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    assert hi[2] - lo[2] == pytest.approx(0.85, abs=1e-4)      # altura real de la categoria
    assert lo[2] == pytest.approx(0.0, abs=1e-5)               # base en el suelo
    assert (lo[0] + hi[0]) / 2 == pytest.approx(0.0, abs=1e-4) and (lo[1] + hi[1]) / 2 == pytest.approx(0.0, abs=1e-4)
    assert rep["cleaned"]["fragment_faces"] >= 1               # el triangulo flotante se fue
    bm = _bm(obj)
    assert not any(len(v.link_faces) == 0 for v in bm.verts)   # sin vertices sueltos
    bm.free()
    assert tuple(obj.location) == (0, 0, 0) and tuple(obj.scale) == (1, 1, 1)


def _bm(obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    return bm


def test_normals_point_outward(tmp_path):
    obj, _ = postprocess.process(fake_obj(tmp_path), "B", opts(category="barril", pivot="center"))
    bm = _bm(obj)
    bm.faces.ensure_lookup_table()
    inside = sum(1 for f in bm.faces if f.normal.dot(f.calc_center_median()) < 0)
    bm.free()
    assert inside == 0


def test_pivot_center_and_keep(tmp_path):
    obj, _ = postprocess.process(fake_obj(tmp_path), "B", opts(category="barril", pivot="center"))
    pts = meshutil.world_points(obj)
    assert (pts[:, 2].min() + pts[:, 2].max()) / 2 == pytest.approx(0.0, abs=1e-4)


def test_manual_budget_reduces(tmp_path):
    obj, rep = postprocess.process(fake_obj(tmp_path), "B", opts(budget="manual", min_tris=20, max_tris=80, category="barril"))
    assert rep["reduced_from"] > 80 and rep["tris"] <= 90
    assert not rep["warnings"]


def test_budget_min_warns(tmp_path):
    _obj, rep = postprocess.process(fake_obj(tmp_path), "B", opts(budget="manual", min_tris=5000, max_tris=9000))
    assert any("minimo" in w for w in rep["warnings"])


def test_auto_budget_keeps_small_mesh(tmp_path):
    _obj, rep = postprocess.process(fake_obj(tmp_path), "B", opts(category="barril"))
    assert rep["tris"] == rep["reduced_from"]


def test_validation():
    with pytest.raises(PFError):
        postprocess.Options(category="nave").validate()
    with pytest.raises(PFError):
        postprocess.Options(budget="manual", min_tris=10, max_tris=5).validate()
    with pytest.raises(PFError):
        postprocess.Options(material="plastico").validate()


def test_missing_and_bad_files(tmp_path):
    with pytest.raises(PFError):
        postprocess.import_mesh(tmp_path / "no.obj")
    bad = tmp_path / "a.stl"
    bad.write_text("x")
    with pytest.raises(PFError):
        postprocess.import_mesh(bad)


def test_failure_leaves_no_orphan_object(tmp_path):
    before = len(bpy.data.objects)
    with pytest.raises(PFError):
        postprocess.process(fake_obj(tmp_path), "B", opts(material="ia"))     # sin texturas ni color
    assert len(bpy.data.objects) == before
