"""Exporta un informe de estilo de la escena de Blender y lo copia al portapapeles.

Uso: abre la pestana "Scripting" de Blender, crea un texto nuevo, pega este
archivo y pulsa "Run Script". Despues pega el resultado (Ctrl+V) en el chat.

Solo lee la escena: no modifica nada.
"""
import json

import bpy

ONLY_SELECTED = False  # True = solo objetos seleccionados
MAX_OBJECTS = 60       # limite para que el informe no sea enorme

MODIFIER_KEYS = {
    "BEVEL": ["width", "segments", "limit_method", "angle_limit"],
    "SUBSURF": ["levels", "render_levels"],
    "ARRAY": ["count"],
    "MIRROR": ["use_axis"],
    "SOLIDIFY": ["thickness"],
    "WEIGHTED_NORMAL": [],
    "DECIMATE": ["ratio"],
}


def r(v, n=4):
    return round(float(v), n)


def modifier_info(mod):
    info = {"type": mod.type, "name": mod.name}
    for key in MODIFIER_KEYS.get(mod.type, []):
        try:
            val = getattr(mod, key)
            info[key] = list(val) if hasattr(val, "__len__") and not isinstance(val, str) else val
        except Exception:
            pass
    return info


def material_info(mat):
    info = {"name": mat.name, "base_color": None, "metallic": None,
            "roughness": None, "textures": []}
    tree = getattr(mat, "node_tree", None)
    if tree is None:
        info["base_color"] = [r(c, 3) for c in mat.diffuse_color]
        return info
    for node in tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            try:
                info["base_color"] = [r(c, 3) for c in node.inputs["Base Color"].default_value]
                info["metallic"] = r(node.inputs["Metallic"].default_value, 3)
                info["roughness"] = r(node.inputs["Roughness"].default_value, 3)
            except Exception:
                pass
        elif node.type == "TEX_IMAGE" and node.image is not None:
            info["textures"].append({"image": node.image.name,
                                     "size": list(node.image.size)})
    return info


def object_info(obj, depsgraph):
    mesh = None
    verts = tris = 0
    try:
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        verts = len(mesh.vertices)
        tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
        eval_obj.to_mesh_clear()
    except Exception:
        pass
    return {
        "name": obj.name,
        "parent": obj.parent.name if obj.parent else None,
        "collections": [c.name for c in obj.users_collection],
        "dimensions_m": [r(d) for d in obj.dimensions],
        "location": [r(v) for v in obj.location],
        "scale": [r(v) for v in obj.scale],
        "tris": tris,
        "verts": verts,
        "uv_layers": len(obj.data.uv_layers) if obj.type == "MESH" else 0,
        "modifiers": [modifier_info(m) for m in obj.modifiers],
        "materials": [material_info(s.material) for s in obj.material_slots if s.material],
    }


def main():
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    pool = bpy.context.selected_objects if ONLY_SELECTED else scene.objects
    meshes = [o for o in pool if o.type == "MESH"][:MAX_OBJECTS]
    report = {
        "blender_version": bpy.app.version_string,
        "unit_system": scene.unit_settings.system,
        "unit_scale": r(scene.unit_settings.scale_length),
        "object_count": len(meshes),
        "total_tris": 0,
        "objects": [],
    }
    for obj in meshes:
        info = object_info(obj, depsgraph)
        report["total_tris"] += info["tris"]
        report["objects"].append(info)

    text = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    bpy.context.window_manager.clipboard = text
    block = bpy.data.texts.get("style_report.json") or bpy.data.texts.new("style_report.json")
    block.clear()
    block.write(json.dumps(report, ensure_ascii=False, indent=1))
    print("Informe copiado al portapapeles: %d objetos, %d tris, %d caracteres"
          % (report["object_count"], report["total_tris"], len(text)))


main()
