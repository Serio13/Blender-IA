import bpy
import pytest

import helpers
from pirate_prop_forge.core import assets, lods, meshutil
from pirate_prop_forge.core.settings import lod_settings
from pirate_prop_forge.core.errors import PFError


def _asset(*objs):
    return assets.find_assets([o.name for o in objs])[0]


def _near(value, target, tol=0.12):
    return abs(value - target) <= tol * target


def test_ratios_hit_targets_and_keep_uvs(chest):
    base, lid, _ = chest
    asset = _asset(base, lid)
    res = lods.generate_lods(asset, lod_settings("estandar", dissolve_deg=0))
    t0 = res.levels[0].tris
    assert len(res.levels) == 3
    assert _near(res.levels[1].tris, t0 * 0.35) and _near(res.levels[2].tris, t0 * 0.10)
    for lv in res.levels[1:]:
        for obj in lv.objects:
            assert len(obj.data.uv_layers) == 2
            assert obj["pf_asset"] == "Cofre_test" and obj["pf_lod"] == lv.index


def test_dimensions_are_preserved(chest):
    base, lid, _ = chest
    asset = _asset(base, lid)
    res = lods.generate_lods(asset, lod_settings("estandar", dissolve_deg=0))
    lo0, hi0 = meshutil.objects_bounds(res.levels[0].objects)
    for lv in res.levels[1:]:
        lo, hi = meshutil.objects_bounds(lv.objects)
        assert abs((hi - lo) - (hi0 - lo0)).max() < 0.02


def test_uv_coordinates_stay_valid():
    mat = helpers.make_material("Barril_u")
    barrel = helpers.make_barrel("Barril_u_malla_BAKED", material=mat, segs=64, rings=48)
    res = lods.generate_lods(_asset(barrel), lod_settings("completo"))
    assert len(res.levels) == 4
    import numpy as np
    for lv in res.levels[1:]:
        uv = lv.objects[0].data.uv_layers[0].data
        arr = np.empty(len(uv) * 2, dtype=np.float32)
        uv.foreach_get("uv", arr)
        assert np.isfinite(arr).all() and arr.min() > -0.5 and arr.max() < 1.5


def test_planar_dissolve_levels_that_do_not_reduce_are_dropped(chest):
    base, lid, _ = chest
    res = lods.generate_lods(_asset(base, lid), lod_settings("estandar"))
    assert len(res.levels) == 2  # el disuelto ya lo deja en ~7 %: LOD2 no mejora
    assert any("omitido" in n for n in res.notes)


def test_small_assets_skip_lods():
    obj = helpers.make_detailed_box("Moneda_malla", dims=(0.04, 0.04, 0.005), cuts=1, bevel=0.001)
    assert meshutil.tri_count(obj.data) < 500
    res = lods.generate_lods(_asset(obj), lod_settings("estandar", skip_below=500))
    assert len(res.levels) == 1 and res.notes


def test_absolute_triangle_targets(chest):
    base, lid, _ = chest
    res = lods.generate_lods(_asset(base, lid), lod_settings(tris=(4000, 900), dissolve_deg=0))
    assert _near(res.levels[1].tris, 4000) and _near(res.levels[2].tris, 900)


def test_min_tris_drops_tiny_levels(chest):
    base, lid, _ = chest
    res = lods.generate_lods(_asset(base, lid), lod_settings(tris=(4000, 10), dissolve_deg=0))
    assert len(res.levels) == 2


def test_regenerating_replaces_previous_lods(chest):
    base, lid, _ = chest
    asset = _asset(base, lid)
    s = lod_settings("estandar", dissolve_deg=0)
    lods.generate_lods(asset, s)
    n = len([o for o in bpy.data.objects if o.get("pf_lod")])
    lods.generate_lods(asset, s)
    assert len([o for o in bpy.data.objects if o.get("pf_lod")]) == n == 4
    assert lods.clear_lods(asset) == 4
    assert not [o for o in bpy.data.objects if o.get("pf_lod")]


def test_originals_are_untouched(chest):
    base, lid, _ = chest
    before = (len(base.data.polygons), tuple(base.location), base.data.name)
    lods.generate_lods(_asset(base, lid), lod_settings("estandar", dissolve_deg=0))
    assert (len(base.data.polygons), tuple(base.location), base.data.name) == before


def test_spread_offsets_levels_in_x(chest):
    base, lid, _ = chest
    res = lods.generate_lods(_asset(base, lid), lod_settings("estandar", dissolve_deg=0, spread=True))
    xs = [lv.objects[0].matrix_world.translation.x for lv in res.levels]
    assert xs[0] < xs[1] < xs[2]
    assert list(res.levels[1].objects[0]["pf_offset"])[0] > 0


def test_drop_extra_uv_option(chest):
    base, lid, _ = chest
    res = lods.generate_lods(_asset(base, lid), lod_settings("estandar", dissolve_deg=0, keep_uv2=False))
    assert all(len(o.data.uv_layers) == 1 for o in res.levels[1].objects)


def test_flat_shading_is_inherited():
    mat = helpers.make_material("Caja_f")
    box = helpers.make_detailed_box("Caja_f_malla_BAKED", cuts=10, flat=True, material=mat)
    res = lods.generate_lods(_asset(box), lod_settings("estandar", dissolve_deg=0))
    assert not any(p.use_smooth for p in res.levels[1].objects[0].data.polygons)


def test_invalid_settings():
    with pytest.raises(PFError):
        lod_settings("nope")
    with pytest.raises(PFError):
        lod_settings(ratios=(1.5,))
