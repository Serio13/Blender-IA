import json
from pathlib import Path

import bpy
import numpy as np
import pytest

import helpers
from pngread import read_png
from pirate_prop_forge.core import assets, export, lods
from pirate_prop_forge.core.errors import PFError
from pirate_prop_forge.core.settings import lod_settings


def _read_png(path, srgb=False):
    return read_png(path)


def _strip(name):
    return name.split(".")[0] if name[-4:-3] == "." else name


def _run(chest, tmp_path, **opt):
    base, lid, _ = chest
    asset = assets.find_assets([base.name, lid.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", dissolve_deg=0))
    kw = dict(verify=True)
    kw.update(opt)
    rep = export.export_asset(asset, tmp_path, res, export.ExportOptions(**kw))
    return asset, res, rep


def test_package_layout(chest, tmp_path):
    _, _, rep = _run(chest, tmp_path)
    pkg = tmp_path / "Cofre_test"
    names = sorted(p.name for p in pkg.rglob("*") if p.is_file())
    assert names == ["Cofre_test.blend", "Cofre_test.fbx", "Cofre_test_BaseMap.png",
                     "Cofre_test_MetallicSmoothness.png", "Cofre_test_Normal.png", "Cofre_test_report.json"]
    assert (pkg / "Textures" / "Cofre_test_BaseMap.png").exists()
    report = json.loads((pkg / "Cofre_test_report.json").read_text(encoding="utf-8"))
    assert report["asset"] == "Cofre_test" and len(report["lods"]) == 3
    props = report["unity_material"]["properties"]
    assert props["_BaseMap"] == "Textures/Cofre_test_BaseMap.png"
    assert props["_MetallicGlossMap"] == "Textures/Cofre_test_MetallicSmoothness.png"
    assert props["_BumpMap"].endswith("Normal.png")
    assert report["unity_lod_screen_heights"] == [0.5, 0.2]


def test_fbx_nodes_origin_and_pivot(chest, tmp_path):
    _, _, rep = _run(chest, tmp_path)
    v = rep["verify"]
    nodes = {_strip(n) for n in v["nodes"]}
    assert {"Cofre_test_LOD0", "Cofre_test_LOD1", "Cofre_test_LOD2",
            "Cofre_test_base_LOD0", "Cofre_test_tapa_LOD2"} <= nodes
    # el ancla (base) del asset estaba en (5, 3, 0) y debe quedar en el origen
    lo, hi = v["bounds"]["min"], v["bounds"]["max"]
    assert lo == pytest.approx([-0.36, -0.24, 0.0], abs=0.01)
    assert hi == pytest.approx([0.36, 0.70, 0.55], abs=0.01)
    # tris por LOD0 conservados en el FBX
    assert v["tris"]["Cofre_test_base_LOD0"] == 7452


def test_exact_node_names_even_when_blender_has_same_names(chest, tmp_path):
    base, lid, _ = chest
    asset = assets.find_assets([base.name, lid.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", dissolve_deg=0))
    before = sorted(o.name for o in bpy.data.objects)
    rep = export.export_asset(asset, tmp_path, res, export.ExportOptions())
    assert all("." not in n for lv in rep["nodes"].values() for n in lv)
    assert sorted(o.name for o in bpy.data.objects) == before  # nombres restaurados
    assert not [m for m in bpy.data.materials if m.name.startswith("M_")]
    assert not [c for c in bpy.data.collections if c.name != "PF_LODS"]


def test_metallic_smoothness_packing(chest, tmp_path):
    _run(chest, tmp_path, formats=("fbx",))
    arr = _read_png(tmp_path / "Cofre_test" / "Textures" / "Cofre_test_MetallicSmoothness.png")
    assert arr[..., 0].mean() == pytest.approx(0.25, abs=0.02)   # metallic
    assert arr[..., 3].mean() == pytest.approx(0.40, abs=0.02)   # smoothness = 1 - roughness


def test_basecolor_and_normal_are_raw(chest, tmp_path):
    _run(chest, tmp_path, formats=("fbx",))
    normal = _read_png(tmp_path / "Cofre_test" / "Textures" / "Cofre_test_Normal.png")
    assert normal[..., 0].mean() == pytest.approx(0.5, abs=0.01)
    assert normal[..., 2].mean() == pytest.approx(1.0, abs=0.01)
    base = _read_png(tmp_path / "Cofre_test" / "Textures" / "Cofre_test_BaseMap.png", srgb=True)
    assert base[..., 2].mean() == pytest.approx(0.3, abs=0.02)


def test_blend_can_be_appended(chest, tmp_path):
    _run(chest, tmp_path, formats=("blend",))
    path = tmp_path / "Cofre_test" / "Cofre_test.blend"
    with bpy.data.libraries.load(str(path)) as (src, _dst):
        assert "Cofre_test" in src.collections
        assert "M_Cofre_test" in src.materials


def test_collider_hint_and_mesh(chest, tmp_path):
    _, _, rep = _run(chest, tmp_path, collider="mesh")
    box = rep["collider"]["hint"]["box"]
    assert box["size_unity"] == pytest.approx([0.72, 0.55, 0.94], abs=0.01)
    assert box["center_blender"] == pytest.approx([0.0, 0.23, 0.275], abs=0.01)
    assert rep["collider"]["mesh"]["tris"] <= 48
    assert any(_strip(n) == "Cofre_test_COL" for n in rep["verify"]["nodes"])


def test_no_collider_option(chest, tmp_path):
    _, _, rep = _run(chest, tmp_path, collider="none")
    assert rep["collider"] is None
    assert not any("_COL" in n for n in rep["verify"]["nodes"])


def test_flat_layout_has_no_lod_empties(chest, tmp_path):
    _, _, rep = _run(chest, tmp_path, layout="flat")
    nodes = {_strip(n) for n in rep["verify"]["nodes"]}
    assert "Cofre_test_LOD0" not in nodes and "Cofre_test_base_LOD1" in nodes


def test_single_part_without_lods_has_plain_names(tmp_path):
    mat = helpers.make_material("Moneda")
    obj = helpers.make_detailed_box("Moneda_malla_BAKED", dims=(0.04, 0.04, 0.005), cuts=1, material=mat)
    asset = assets.find_assets([obj.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", skip_below=1000))
    rep = export.export_asset(asset, tmp_path, res, export.ExportOptions(verify=True))
    assert [_strip(n) for n in rep["verify"]["nodes"]] == ["Moneda"]


def test_scale_and_rotation_of_source_are_normalized(tmp_path):
    mat = helpers.make_material("Barril_s")
    barrel = helpers.make_barrel("Barril_s_malla_BAKED", loc=(3, 4, 1), material=mat, segs=24, rings=16)
    barrel.scale = (2.0, 2.0, 2.0)
    barrel.rotation_euler = (0, 0, 1.0)
    bpy.context.view_layer.update()
    asset = assets.find_assets([barrel.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", skip_below=100))
    rep = export.export_asset(asset, tmp_path, res, export.ExportOptions(verify=True))
    lo, hi = rep["verify"]["bounds"]["min"], rep["verify"]["bounds"]["max"]
    size = [h - l for l, h in zip(lo, hi)]
    # radio 0.3 * 2 = 0.6 -> diametro 1.2 ; alto 0.8*... se conserva el tamano visual (escala aplicada)
    assert size[0] == pytest.approx(1.2, abs=0.03) and size[1] == pytest.approx(1.2, abs=0.03)
    assert (lo[0] + hi[0]) / 2 == pytest.approx(0.0, abs=0.02)


def test_missing_textures_warn(tmp_path):
    obj = helpers.make_detailed_box("Roca_malla_BAKED", cuts=2)
    asset = assets.find_assets([obj.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", skip_below=100))
    rep = export.export_asset(asset, tmp_path, res, export.ExportOptions())
    assert any("texturas" in w for w in rep["warnings"])


def test_metallic_and_roughness_with_different_sizes(tmp_path):
    mat = bpy.data.materials.new("TXB_Raro")
    for kind, size, kindname in (("Metallic", 32, "metal"), ("Roughness", 64, "rough")):
        img = helpers.make_image("TX_Raro_%s" % kind, size, kindname)
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
    obj = helpers.make_detailed_box("Raro_malla_BAKED", cuts=2, material=mat)
    asset = assets.find_assets([obj.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", skip_below=100))
    rep = export.export_asset(asset, tmp_path, res, export.ExportOptions(formats=("fbx",)))
    assert any("distinto tamano" in w for w in rep["warnings"])
    assert rep["textures"][0]["size"] == [64, 64]


def test_invalid_options():
    with pytest.raises(PFError):
        export.ExportOptions(layout="x").validate()
    with pytest.raises(PFError):
        export.ExportOptions(collider="x").validate()
    with pytest.raises(PFError):
        export.ExportOptions(formats=("obj",)).validate()


def test_images_loaded_from_files_and_packed(tmp_path):
    """Caso real: PNG cargados desde disco y empaquetados (source FILE), como en los .blend de produccion."""
    src = tmp_path / "src"
    src.mkdir()
    mat = bpy.data.materials.new("TXB_Real")
    for kind, name, val in (("color", "BaseColor", None), ("normal", "Normal", None),
                            ("metal", "Metallic", 0.8), ("rough", "Roughness", 0.2)):
        gen = helpers.make_image("tmp_" + name, 32, kind, packed=False, value=val)
        gen.filepath_raw = str(src / (name + ".png"))
        gen.file_format = "PNG"
        gen.save()
        bpy.data.images.remove(gen)
        img = bpy.data.images.load(str(src / (name + ".png")))
        img.name = "TX_Real_" + name
        if kind != "color":
            img.colorspace_settings.name = "Non-Color"
        img.pack()
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
    obj = helpers.make_detailed_box("Real_malla_BAKED", cuts=4, material=mat)
    asset = assets.find_assets([obj.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", skip_below=100))
    export.export_asset(asset, tmp_path / "out", res, export.ExportOptions(formats=("fbx",)))
    ms = _read_png(tmp_path / "out" / "Real" / "Textures" / "Real_MetallicSmoothness.png")
    assert ms[..., 0].mean() == pytest.approx(0.8, abs=0.02)
    assert ms[..., 3].mean() == pytest.approx(0.8, abs=0.02)      # 1 - 0.2


def test_empty_images_are_skipped_with_a_warning(tmp_path):
    mat = bpy.data.materials.new("TXB_Vacia")
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.new("TX_Vacia_BaseColor", 4, 4)
    node.image.source = "FILE"
    node.image.filepath = "//no_existe.png"
    obj = helpers.make_detailed_box("Vacia_malla_BAKED", cuts=2, material=mat)
    asset = assets.find_assets([obj.name])[0]
    res = lods.generate_lods(asset, lod_settings("estandar", skip_below=100))
    rep = export.export_asset(asset, tmp_path, res, export.ExportOptions(formats=("fbx",)))
    assert any("vacia" in w for w in rep["warnings"]) or rep["textures"] == []


def test_modifiers_on_sources_are_noted(chest):
    base, lid, _ = chest
    base.modifiers.new("b", "BEVEL")
    res = lods.generate_lods(assets.find_assets([base.name, lid.name])[0], lod_settings("estandar", dissolve_deg=0))
    assert any("modificadores" in n for n in res.notes)
