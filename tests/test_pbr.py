import bpy
import numpy as np
import pytest

import helpers
from pirate_prop_forge.core import pbr, postprocess, textures


def raw_barrel(tmp_path):
    from test_postprocess import fake_obj
    return fake_obj(tmp_path)


def px(img):
    return pbr._read(img)


def test_procedural_bake_makes_one_material_and_four_textures(tmp_path):
    obj, rep = postprocess.process(raw_barrel(tmp_path), "Barril_ia_V2",
                                   postprocess.Options(category="barril", material="madera", tex_size=256))
    assert [m.name for m in obj.data.materials] == ["TXB_Barril_ia_V2"]
    assert rep["material"] == "TXB_Barril_ia_V2" and "UV generadas" in rep["notes"]
    names = sorted(i.name for i in bpy.data.images if i.name.startswith("TX_"))
    assert names == ["TX_Barril_ia_V2_" + k for k in ("BaseColor", "Metallic", "Normal", "Roughness")]
    color = px(bpy.data.images["TX_Barril_ia_V2_BaseColor"])
    assert color[..., :3].max() > 0.05 and color[..., 0].std() > 0.005            # hay color y variacion
    rough = px(bpy.data.images["TX_Barril_ia_V2_Roughness"])
    assert 0.2 < rough[..., 0].mean() < 0.9
    normal = px(bpy.data.images["TX_Barril_ia_V2_Normal"])
    assert normal[..., 2].mean() > 0.5                                           # normal tangente (azulada)
    assert all(i.packed_file for i in bpy.data.images if i.name.startswith("TX_"))
    assert not [m for m in bpy.data.materials if m.name.startswith("PFTMP")]     # sin restos temporales


def test_presets_differ(tmp_path):
    means = {}
    for preset in ("madera", "cuero", "metal"):
        helpers.reset_scene()
        postprocess.process(raw_barrel(tmp_path), "A", postprocess.Options(category="barril", material=preset, tex_size=128))
        means[preset] = px(bpy.data.images["TX_A_BaseColor"])[..., :3].mean(axis=(0, 1))
        if preset == "metal":
            assert px(bpy.data.images["TX_A_Metallic"])[..., 0].mean() > 0.5
        else:
            assert px(bpy.data.images["TX_A_Metallic"])[..., 0].mean() < 0.01
    assert means["madera"][0] > means["metal"][0] * 1.2                          # la madera es mas calida
    assert not np.allclose(means["madera"], means["cuero"], atol=0.01)


def test_custom_color(tmp_path):
    postprocess.process(raw_barrel(tmp_path), "A", postprocess.Options(category="barril", material="cuero", tex_size=128,
                                                                       color=(0.02, 0.02, 0.5)))
    m = px(bpy.data.images["TX_A_BaseColor"])[..., :3].mean(axis=(0, 1))
    assert m[2] > m[0] * 2


def test_kind_names_are_understood_by_exporter(tmp_path):
    obj, _ = postprocess.process(raw_barrel(tmp_path), "A", postprocess.Options(category="barril", material="madera", tex_size=128))
    found, unknown = textures.collect_images([obj])
    assert set(found) == {"BaseMap", "Normal", "Metallic", "Roughness"} and not unknown


def test_vertex_colors_are_baked(tmp_path):
    from pirate_prop_forge.core import meshutil
    obj = postprocess.import_mesh(raw_barrel(tmp_path))
    attr = obj.data.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    n = len(obj.data.loops)
    vals = np.tile(np.array([0.8, 0.1, 0.1, 1.0], np.float32), n)
    attr.data.foreach_set("color", vals)
    obj.name = "A_malla_BAKED"
    mat, made_uv = pbr.bake_vertex_colors(obj, "A", 128)
    assert made_uv and mat.name == "TXB_A"
    c = px(bpy.data.images["TX_A_BaseColor"])
    lit = c[c[..., :3].sum(axis=-1) > 0.05]
    assert len(lit) > 100 and lit[:, 0].mean() > lit[:, 1].mean() * 2


def test_ai_textures_roundtrip_through_glb(tmp_path):
    cube = helpers.make_detailed_box("Cubo", cuts=1, uv_layers=1)
    mat = bpy.data.materials.new("glbmat")
    tree, links = mat.node_tree, mat.node_tree.links
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    spec = (("BaseColor", "color", "Base Color", None), ("Roughness", "rough", "Roughness", 0.8),
            ("Metallic", "metal", "Metallic", 0.3))
    for kind, imgkind, sock, value in spec:
        img = helpers.make_image("src_" + kind, 32, imgkind, value=value)
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        links.new(node.outputs["Color"], bsdf.inputs[sock])
    nimg = helpers.make_image("src_normal", 32, "normal")
    nnode = tree.nodes.new("ShaderNodeTexImage")
    nnode.image = nimg
    nm = tree.nodes.new("ShaderNodeNormalMap")
    links.new(nnode.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    cube.data.materials.append(mat)
    bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    glb = tmp_path / "ia.glb"
    bpy.ops.object.select_all(action="DESELECT")
    cube.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(glb), use_selection=True, export_format="GLB")
    helpers.reset_scene()
    obj, rep = postprocess.process(glb, "Caja_ia", postprocess.Options(category="caja", material="ia", pivot="base"))
    assert rep["material"] == "TXB_Caja_ia" and not rep["notes"]
    rough = px(bpy.data.images["TX_Caja_ia_Roughness"])[..., 0].mean()
    metal = px(bpy.data.images["TX_Caja_ia_Metallic"])[..., 0].mean()
    assert rough == pytest.approx(0.8, abs=0.03) and metal == pytest.approx(0.3, abs=0.03)
    assert bpy.data.images["TX_Caja_ia_Normal"].colorspace_settings.name == "Non-Color"
    assert bpy.data.images["TX_Caja_ia_BaseColor"].colorspace_settings.name == "sRGB"
    assert not [i for i in bpy.data.images if not i.name.startswith("TX_")]
