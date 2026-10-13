import bmesh
import bpy
import numpy as np
import pytest

import helpers
from pirate_prop_forge import api
from pirate_prop_forge.core import assets, lods, quality
from pirate_prop_forge.core.settings import lod_settings


def _shift_uv(mesh, delta):
    uv = mesh.uv_layers[0].data
    arr = np.empty(len(uv) * 2, np.float32)
    uv.foreach_get("uv", arr)
    uv.foreach_set("uv", arr + delta)


def _barrel(texture_kind="color", value=None, name="Barril_c"):
    mat = bpy.data.materials.new("TXB_" + name)
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = helpers.make_image("TX_%s_BaseColor" % name, 64, texture_kind, value=value)
    obj = helpers.make_barrel(name + "_malla_BAKED", material=mat, segs=48, rings=32)
    return obj


def test_uv_shift_on_a_flat_texture_is_not_a_visible_problem():
    """Un desplazamiento de UV sobre una zona lisa no cambia el color: no debe avisar."""
    obj = _barrel("metal", value=0.4)                  # textura de color plano
    shifted = obj.data.copy()
    _shift_uv(shifted, 0.08)
    texture = quality.load_basemap(obj)
    plain = quality.compare(obj.data, shifted)
    q = quality.compare(obj.data, shifted, texture=texture)
    assert plain["uv_p95"] > 0.1 and quality.warnings_for(1, plain)       # sin textura: avisaria
    assert q["color_p95"] == pytest.approx(0.0, abs=0.01)
    assert quality.warnings_for(1, q) == []


def test_uv_shift_on_a_gradient_texture_is_detected_by_colour():
    obj = _barrel("color")                             # degradado: el color depende de la UV
    shifted = obj.data.copy()
    _shift_uv(shifted, 0.25)
    q = quality.compare(obj.data, shifted, texture=quality.load_basemap(obj))
    assert q["color_p95"] > 0.15
    assert "textura se ve distinta" in quality.warnings_for(2, q)[0]


def _double_wall(radius_out=0.300, gap=0.004, segs=32, rows=8):
    """Dos paredes cilindricas casi pegadas (tabla gruesa): la exterior con la mitad izquierda del atlas, la
    interior (normales hacia dentro) con la derecha."""
    from math import cos, pi, sin
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for wall, (r, flip, u0) in enumerate(((radius_out, False, 0.0), (radius_out - gap, True, 0.5))):
        for j in range(rows):
            for i in range(segs):
                ring = lambda k, m: bm.verts.new((r * cos(2 * pi * m / segs), r * sin(2 * pi * m / segs), 0.8 * k / rows))
                v = [ring(j, i), ring(j, (i + 1) % segs), ring(j + 1, (i + 1) % segs), ring(j + 1, i)]
                if flip:
                    v = v[::-1]
                f = bm.faces.new(v)
                us = [(i / segs), ((i + 1) / segs), ((i + 1) / segs), (i / segs)]
                vs = [j / rows, j / rows, (j + 1) / rows, (j + 1) / rows]
                if flip:
                    us, vs = us[::-1], vs[::-1]
                for loop, u, w in zip(f.loops, us, vs):
                    loop[uv].uv = (u0 + 0.5 * u, w)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return bm


def test_the_other_wall_of_a_thin_plank_is_not_matched():
    """Con la pared interior a 4 mm, un LOD que se hunde 3 mm no debe emparejarse con la pared contraria."""
    ref_bm = _double_wall()
    ref = bpy.data.meshes.new("ref")
    ref_bm.to_mesh(ref)
    ref_bm.free()
    outer_only = _double_wall()
    # el LOD = solo la pared exterior, hundida 3 mm hacia dentro (mas cerca de la interior que de la propia)
    bmesh.ops.delete(outer_only, geom=[f for f in outer_only.faces if f.calc_center_median().length < 0.2999 - 0.0001 and False], context="FACES")
    lod_bm = bmesh.new()
    uv = lod_bm.loops.layers.uv.new("UVMap")
    from math import cos, pi, sin
    segs, rows, r = 32, 8, 0.297
    for j in range(rows):
        for i in range(segs):
            ring = lambda k, m: lod_bm.verts.new((r * cos(2 * pi * m / segs), r * sin(2 * pi * m / segs), 0.8 * k / rows))
            f = lod_bm.faces.new([ring(j, i), ring(j, (i + 1) % segs), ring(j + 1, (i + 1) % segs), ring(j + 1, i)])
            for loop, u, w in zip(f.loops, [i / segs, (i + 1) / segs, (i + 1) / segs, i / segs],
                                  [j / rows, j / rows, (j + 1) / rows, (j + 1) / rows]):
                loop[uv].uv = (0.5 * u, w)
    lod = bpy.data.meshes.new("lod")
    lod_bm.to_mesh(lod)
    lod_bm.free()
    texture = np.zeros((16, 64, 3), np.float32)
    texture[:, :, 0] = np.linspace(0, 1, 64)[None, :]            # el color depende de la U: cada pared es distinta
    q = quality.compare(ref, lod, texture=texture)
    assert q["color_p95"] < 0.05, q


def _real_like_barrel(name="Barril_g"):
    mat = helpers.make_material(name)
    return helpers.make_staved_barrel(name + "_malla_BAKED", material=mat)


def test_a_clean_island_uv_barrel_keeps_all_its_lods_in_strict_mode():
    obj = _real_like_barrel()
    res = lods.generate_lods(assets.find_assets([obj.name])[0], lod_settings("estandar", strict=True))
    assert len(res.levels) == 3 and res.warnings == []
    assert res.levels[1].quality["color_p95"] is not None and res.levels[1].quality["color_p95"] < quality.COLOR_WARN


def test_strict_drops_a_level_that_cannot_be_made_without_distortion(monkeypatch):
    obj = _real_like_barrel()
    monkeypatch.setattr(quality, "warnings_for", lambda level, q: ["LOD%d: la textura se ve distinta (diferencia de color p95 80%%)" % level])
    res = lods.generate_lods(assets.find_assets([obj.name])[0], lod_settings("estandar", strict=True))
    assert len(res.levels) == 1
    assert any("LOD1 omitido" in w and "sin deformarlo" in w for w in res.warnings)
    assert not [o for o in bpy.data.objects if o.get("pf_lod")]          # no deja objetos sueltos


def test_strict_raises_the_target_when_a_retry_passes(monkeypatch):
    obj = _real_like_barrel()
    calls = {"n": 0}

    def flaky(level, q):
        calls["n"] += 1
        return ["LOD%d: la textura se ve distinta (diferencia de color p95 30%%)" % level] if calls["n"] == 1 else []

    monkeypatch.setattr(quality, "warnings_for", flaky)
    res = lods.generate_lods(assets.find_assets([obj.name])[0], lod_settings("estandar", strict=True, dissolve_deg=0))
    assert any("LOD1 subido a" in n for n in res.notes)
    assert res.levels[1].tris == pytest.approx(0.35 * 1.4 * res.levels[0].tris, rel=0.1)   # objetivo x1.4
    assert len([o for o in bpy.data.objects if o.get("pf_lod")]) == sum(len(l.objects) for l in res.levels[1:])


def test_non_strict_keeps_the_level_but_warns(monkeypatch):
    obj = _real_like_barrel()
    monkeypatch.setattr(quality, "warnings_for", lambda level, q: ["LOD%d: la textura se ve distinta" % level])
    res = lods.generate_lods(assets.find_assets([obj.name])[0], lod_settings("estandar", strict=False))
    assert len(res.levels) == 3 and len(res.warnings) == 2


def test_api_shows_the_omitted_level_in_the_one_line_output(monkeypatch):
    _real_like_barrel()
    monkeypatch.setattr(quality, "warnings_for", lambda level, q: ["LOD%d: la forma se aleja del original (p95 9.0%% de la diagonal)" % level])
    out = api.lods("*_BAKED", strict=True)
    assert out.count("\n") == 0 and "AVISO: LOD1 omitido" in out
