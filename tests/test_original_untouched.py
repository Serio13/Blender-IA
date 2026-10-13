"""El original NO debe cambiar al generar LODs o exportar, y los LODs no deben taparlo en el visor."""
import hashlib

import bpy
import numpy as np

import helpers
from pirate_prop_forge import api


def _digest(arr):
    return hashlib.sha1(np.ascontiguousarray(arr).tobytes()).hexdigest()


def snapshot():
    """Estado completo de los objetos originales (no generados), sus mallas, materiales e imagenes."""
    state = {"objects": {}, "images": {}, "materials": {}}
    bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.get("pf_generated"):
            continue
        info = {"matrix": tuple(round(v, 6) for row in obj.matrix_world for v in row),
                "hide_viewport": obj.hide_viewport, "hide_render": obj.hide_render, "hide": obj.hide_get() if obj.name in bpy.context.view_layer.objects else None,
                "parent": obj.parent.name if obj.parent else None,
                "modifiers": [m.type for m in obj.modifiers]}
        if obj.type == "MESH":
            m = obj.data
            co = np.empty(len(m.vertices) * 3, np.float32)
            m.vertices.foreach_get("co", co)
            info["mesh"] = (m.name, len(m.vertices), len(m.polygons), _digest(co))
            info["uv"] = [(l.name, l.active_render, _digest(_arr(l, m))) for l in m.uv_layers]
            info["uv_active_index"] = m.uv_layers.active_index if len(m.uv_layers) else None
            info["materials"] = [s.material.name if s.material else None for s in obj.material_slots]
            info["smooth"] = sum(p.use_smooth for p in m.polygons)
        state["objects"][obj.name] = info
    for img in bpy.data.images:
        arr = np.empty(img.size[0] * img.size[1] * 4, np.float32)
        img.pixels.foreach_get(arr) if arr.size else None
        state["images"][img.name] = (tuple(img.size), img.colorspace_settings.name, img.alpha_mode,
                                     img.packed_file is not None, img.filepath, _digest(arr))
    for mat in bpy.data.materials:
        tree = mat.node_tree
        state["materials"][mat.name] = (
            sorted((n.name, n.type, n.image.name if n.type == "TEX_IMAGE" and n.image else None) for n in tree.nodes),
            sorted((l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name) for l in tree.links),
            tree.nodes.active.name if tree.nodes.active else None)   # users no: los LODs comparten el material
    return state


def _arr(layer, mesh):
    a = np.empty(len(mesh.loops) * 2, np.float32)
    layer.data.foreach_get("uv", a)
    return a


def _scene_with_two_layer_chest():
    base, lid, mat = helpers.make_chest(cuts=10)
    for obj in (base, lid):
        m = obj.data
        m.uv_layers[0].name, m.uv_layers[1].name = "UVMap", "Bake"
        m.uv_layers[0].active_render, m.uv_layers[1].active_render = False, True   # la de render NO es la primera
        m.uv_layers.active_index = 0
    return base, lid


def test_generating_lods_and_exporting_never_modify_the_original(tmp_path):
    _scene_with_two_layer_chest()
    before = snapshot()
    api.lods("*_BAKED", strict=False, dissolve_deg=0)
    api.export("*_BAKED", out_dir=str(tmp_path), strict=False, dissolve_deg=0, collider="mesh", verify=True)
    api.export("*_BAKED", out_dir=str(tmp_path), strict=False, dissolve_deg=0, regenerate=True, pivot="center")
    after = snapshot()
    assert after["objects"] == before["objects"]
    assert after["images"] == before["images"]
    assert after["materials"] == before["materials"]


def test_lods_do_not_cover_the_original_in_the_viewport():
    base, lid, _ = helpers.make_chest(cuts=10)
    api.lods("*_BAKED", strict=False, dissolve_deg=0)
    lod_objs = [o for o in bpy.data.objects if o.get("pf_lod")]
    assert lod_objs and all(o.hide_viewport and o.hide_render for o in lod_objs)
    assert not base.hide_viewport and not lid.hide_viewport


def test_spread_makes_the_lods_visible_beside_the_original():
    helpers.make_chest(cuts=10)
    api.lods("*_BAKED", strict=False, dissolve_deg=0, spread=True)
    lod_objs = [o for o in bpy.data.objects if o.get("pf_lod")]
    assert lod_objs and not any(o.hide_viewport for o in lod_objs)


def test_hidden_lods_still_export_in_the_right_place(tmp_path):
    helpers.make_chest(cuts=10)
    api.lods("*_BAKED", strict=False, dissolve_deg=0)
    out = api.export("*_BAKED", out_dir=str(tmp_path), strict=False, verify=True, formats=("fbx",))
    import json
    rep = json.loads((tmp_path / "Cofre_test" / "Cofre_test_report.json").read_text(encoding="utf-8"))
    lo, hi = rep["verify"]["bounds"]["min"], rep["verify"]["bounds"]["max"]
    assert lo[2] == 0.0 or abs(lo[2]) < 0.01          # LOD0 apoyado en el suelo
    assert [lv["level"] for lv in rep["lods"]] == [0, 1, 2]
