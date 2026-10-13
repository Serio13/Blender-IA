import bpy
import numpy as np

import helpers
from pirate_prop_forge.core import assets, lods, quality
from pirate_prop_forge.core.settings import lod_settings


def _barrel():
    mat = helpers.make_material("Barril_q")
    return helpers.make_barrel("Barril_q_malla_BAKED", material=mat, segs=64, rings=48)


def test_identical_meshes_have_zero_error():
    b = _barrel()
    q = quality.compare(b.data, b.data)
    assert q["dev_p95"] == 0.0 and q["uv_p95"] == 0.0


def test_uv_shift_is_detected():
    b = _barrel()
    m2 = b.data.copy()
    uv = m2.uv_layers[0].data
    arr = np.empty(len(uv) * 2, np.float32)
    uv.foreach_get("uv", arr)
    uv.foreach_set("uv", arr + 0.08)
    q = quality.compare(b.data, m2)
    assert 0.10 < q["uv_p95"] < 0.12  # 0.08 en U y en V = 0.113
    assert quality.warnings_for(1, q)


def test_shape_change_is_detected():
    b = _barrel()
    m2 = b.data.copy()
    for v in m2.vertices:
        v.co.x *= 1.1
    q = quality.compare(b.data, m2)
    assert q["dev_p95"] > quality.DEV_WARN
    assert any("forma" in w for w in quality.warnings_for(2, q))


def test_good_lods_pass_the_quality_gate():
    b = _barrel()
    asset = assets.find_assets([b.name])[0]
    res = lods.generate_lods(asset, lod_settings("completo"))
    assert len(res.levels) == 4 and res.warnings == []
    for lv in res.levels[1:]:
        assert lv.quality["uv_p95"] < quality.UV_WARN and lv.quality["dev_p95"] < quality.DEV_WARN


def test_no_uv_layers_does_not_crash():
    box = helpers.make_detailed_box("Caja_nouv_malla", cuts=4, uv_layers=0)
    q = quality.compare(box.data, box.data)
    assert q["uv_p95"] is None


def test_worst_aggregates_by_max():
    a = {"dev_p95": 0.001, "dev_max": 0.002, "uv_p95": 0.01, "uv_mean": 0.005}
    b = {"dev_p95": 0.004, "dev_max": 0.003, "uv_p95": None, "uv_mean": None}
    w = quality.worst([a, b])
    assert w == {"dev_p95": 0.004, "dev_max": 0.003, "uv_p95": 0.01, "uv_mean": 0.005}
