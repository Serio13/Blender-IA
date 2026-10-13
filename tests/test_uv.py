"""Caso real: assets con dos capas UV donde la de render (la que usan las texturas) NO es la primera.

Blender muestra bien la textura (usa la capa de render), pero Unity usa siempre la primera capa del FBX:
el resultado era un mosaico de la textura. La capa que usan las texturas debe ir primera.
"""
import bpy
import numpy as np
import pytest

import helpers
from pirate_prop_forge import api
from pirate_prop_forge.core import assets, export, lods, meshutil, textures
from helpers import lod_settings


def _uv(mesh, i):
    layer = mesh.uv_layers[i]
    arr = np.empty(len(mesh.loops) * 2, np.float32)
    layer.data.foreach_get("uv", arr)
    return arr


def _two_layer_box(name="Barril_uv", render_index=1, cuts=6, material=True):
    """Capa 0 = 'UVMap' (proyeccion tosca); capa 1 = 'Bake' (distinta). La de render es render_index."""
    mat = helpers.make_material("Barril_uv") if material else None
    obj = helpers.make_detailed_box(name + "_malla_BAKED", cuts=cuts, material=mat, uv_layers=2)
    m = obj.data
    m.uv_layers[0].name, m.uv_layers[1].name = "UVMap", "Bake"
    shifted = _uv(m, 1) + 0.3
    m.uv_layers[1].data.foreach_set("uv", shifted)
    for i, layer in enumerate(m.uv_layers):
        layer.active_render = (i == render_index)
    return obj


def test_order_puts_the_render_layer_first():
    obj = _two_layer_box()
    expected = _uv(obj.data, 1).copy()
    other = _uv(obj.data, 0).copy()
    first = meshutil.order_uv_layers(obj.data)
    assert first == "Bake" and [l.name for l in obj.data.uv_layers] == ["Bake", "UVMap"]
    assert np.allclose(_uv(obj.data, 0), expected) and np.allclose(_uv(obj.data, 1), other)
    assert obj.data.uv_layers[0].active_render and not obj.data.uv_layers[1].active_render


def test_order_can_drop_the_extra_layers_keeping_the_right_one():
    obj = _two_layer_box()
    expected = _uv(obj.data, 1).copy()
    meshutil.order_uv_layers(obj.data, keep_extra=False)
    assert [l.name for l in obj.data.uv_layers] == ["Bake"] and np.allclose(_uv(obj.data, 0), expected)


def test_nothing_to_do_when_render_layer_is_already_first():
    obj = _two_layer_box(render_index=0)
    before = _uv(obj.data, 0).copy()
    assert meshutil.order_uv_layers(obj.data) == "UVMap"
    assert np.allclose(_uv(obj.data, 0), before)


def test_single_and_no_layers_are_fine():
    assert meshutil.order_uv_layers(helpers.make_detailed_box("A", uv_layers=1).data) == "UVMap"
    assert meshutil.order_uv_layers(helpers.make_detailed_box("B", uv_layers=0).data) is None


def test_uv_map_node_wins_over_active_render():
    """Si el material fuerza una capa con un nodo UV Map, esa es la de las texturas."""
    obj = _two_layer_box(render_index=0)          # render = UVMap, pero el material usa 'Bake'
    mat = obj.data.materials[0]
    node = next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE")
    uvnode = mat.node_tree.nodes.new("ShaderNodeUVMap")
    uvnode.uv_map = "Bake"
    mat.node_tree.links.new(uvnode.outputs["UV"], node.inputs["Vector"])
    assert textures.render_uv_name([obj]) == "Bake"
    expected = _uv(obj.data, 1).copy()
    meshutil.order_uv_layers(obj.data, "Bake")
    assert obj.data.uv_layers[0].name == "Bake" and np.allclose(_uv(obj.data, 0), expected)


def test_uv_map_node_behind_a_mapping_node_is_found():
    obj = _two_layer_box(render_index=0)
    mat = obj.data.materials[0]
    tree = mat.node_tree
    node = next(n for n in tree.nodes if n.type == "TEX_IMAGE")
    uvnode, mapping = tree.nodes.new("ShaderNodeUVMap"), tree.nodes.new("ShaderNodeMapping")
    uvnode.uv_map = "Bake"
    tree.links.new(uvnode.outputs["UV"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
    assert textures.render_uv_name([obj]) == "Bake"


def _two_layer_barrel():
    """Barril con UV suaves (el control de calidad no da falsos avisos) y dos capas, la de render la segunda."""
    mat = helpers.make_material("Barril_s2")
    obj = helpers.make_barrel("Barril_s2_malla_BAKED", material=mat, segs=64, rings=48, uv_layers=2)
    m = obj.data
    m.uv_layers[0].name, m.uv_layers[1].name = "UVMap", "Bake"
    m.uv_layers[1].data.foreach_set("uv", _uv(m, 1) + 0.3)
    m.uv_layers[0].active_render, m.uv_layers[1].active_render = False, True
    m.uv_layers.active_index = 0   # la capa activa de edicion NO es la de render: caso real
    return obj


def test_lods_keep_the_render_layer_first_and_quality_compares_it():
    obj = _two_layer_barrel()
    asset = assets.find_assets([obj.name])[0]
    res = lods.generate_lods(asset, lod_settings("completo"))
    assert len(res.levels) == 4 and res.warnings == []
    for lv in res.levels[1:]:
        assert lv.objects[0].data.uv_layers[0].name == "Bake"
        assert lv.quality["uv_p95"] < 0.02   # si se compararan capas distintas saldria ~0.42


def test_lods_drop_uv2_keeps_the_render_layer():
    obj = _two_layer_box(cuts=10)
    expected = _uv(obj.data, 1).copy()
    asset = assets.find_assets([obj.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", dissolve_deg=0, keep_uv2=False))
    lod = res.levels[1].objects[0].data
    assert [l.name for l in lod.uv_layers] == ["Bake"]


def _first_uv_of_reimported_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    lod0 = next(o for o in meshes if o.name.split(".")[0].endswith("_LOD0") or "_LOD" not in o.name)
    return [l.name for l in lod0.data.uv_layers], _uv(lod0.data, 0)


def test_exported_fbx_has_the_render_layer_as_first_uv(tmp_path):
    obj = _two_layer_box(cuts=8)
    expected_mean = float(_uv(obj.data, 1).mean())
    wrong_mean = float(_uv(obj.data, 0).mean())
    assert abs(expected_mean - wrong_mean) > 0.2
    asset = assets.find_assets([obj.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", dissolve_deg=0))
    rep = export.export_asset(asset, tmp_path, res, export.ExportOptions(formats=("fbx",)))
    names, first = _first_uv_of_reimported_fbx(tmp_path / "Barril_uv" / "Barril_uv.fbx")
    assert float(first.mean()) == pytest.approx(expected_mean, abs=0.01)
    assert rep["uv_order"] == ["Bake", "UVMap"] and rep["uv_render"] == "Bake"


def test_check_reports_uv_layers(chest):
    obj = _two_layer_box()
    line = api.check(obj.name).splitlines()[1]
    assert "UV: UVMap, Bake*" in line     # el asterisco marca la capa que usan las texturas
    assert "se pondra primera" in line


def test_check_is_quiet_when_uv_is_already_right():
    obj = _two_layer_box(render_index=0)
    line = api.check(obj.name).splitlines()[1]
    assert "UV: UVMap*, Bake" in line and "se pondra primera" not in line
