"""Exporta un informe de estilo de la escena de Blender y lo copia al portapapeles.

Uso: abre la pestana "Scripting" de Blender, crea un texto nuevo, pega este
archivo y pulsa "Run Script". Despues pega el resultado (Ctrl+V) en el chat.

Solo lee la escena: no modifica nada.

v2: materiales deduplicados, nodos de materiales clave, mapeo de texturas,
vacios (empties), propiedades personalizadas y altura de la referencia.
"""
import json

import bpy

ONLY_SELECTED = False
MAX_OBJECTS = 400
SKIP_COLLECTIONS = {"REF_pirata", "HOJA_ESTILO"}  # ya analizadas en la v1
REF_COLLECTION = "REF_pirata"                     # para medir la altura de referencia
DEEP_MATERIALS = {"A_wood", "A_wood_dark", "A_iron", "A_gold", "A_cloth_red"}
MAX_NODES_PER_MATERIAL = 40

MODIFIER_KEYS = {
    "BEVEL": ["width", "segments", "limit_method", "angle_limit"],
    "SUBSURF": ["levels", "render_levels"],
    "ARRAY": ["count"],
    "MIRROR": ["use_axis"],
    "SOLIDIFY": ["thickness"],
    "DECIMATE": ["ratio"],
}
NODE_ATTRS = ("blend_type", "data_type", "operation", "projection", "extension",
              "interpolation", "noise_type", "vector_type", "distribution")
PRINCIPLED_KEYS = ("Base Color", "Metallic", "Roughness", "Normal",
                   "Emission Color", "Emission Strength", "Alpha")


def r(v, n=4):
    return round(float(v), n)


def sock_value(sock):
    if sock.is_linked and sock.links:
        link = sock.links[0]
        return "<-%s.%s" % (link.from_node.name, link.from_socket.name)
    val = getattr(sock, "default_value", None)
    if val is None:
        return None
    try:
        return [r(v, 3) for v in val]
    except TypeError:
        return r(val, 3) if isinstance(val, (int, float)) else str(val)


def image_info(img):
    return {"image": img.name, "size": list(img.size),
            "filepath": img.filepath, "packed": img.packed_file is not None}


def node_dump(node):
    d = {"name": node.name, "type": node.type}
    for attr in NODE_ATTRS:
        if hasattr(node, attr):
            try:
                d[attr] = getattr(node, attr)
            except Exception:
                pass
    if node.type == "TEX_IMAGE" and node.image is not None:
        d.update(image_info(node.image))
    ins = {}
    for s in node.inputs:
        if not s.enabled or s.hide:
            continue
        if node.type == "BSDF_PRINCIPLED" and s.name not in PRINCIPLED_KEYS:
            continue
        v = sock_value(s)
        if v is not None:
            ins[s.name] = v
    d["inputs"] = ins
    return d


def node_tree_dump(mat):
    tree = getattr(mat, "node_tree", None)
    if tree is None:
        return None
    nodes = [node_dump(n) for n in list(tree.nodes)[:MAX_NODES_PER_MATERIAL]]
    links = ["%s.%s->%s.%s" % (l.from_node.name, l.from_socket.name,
                               l.to_node.name, l.to_socket.name) for l in tree.links]
    return {"nodes": nodes, "links": links}


def material_info(mat):
    info = {"base_color": None, "metallic": None, "roughness": None, "textures": []}
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
            tex = image_info(node.image)
            tex["projection"] = node.projection
            tex["vector_from"] = sock_value(node.inputs["Vector"]) if "Vector" in node.inputs else None
            info["textures"].append(tex)
    return info


def modifier_info(mod):
    info = {"type": mod.type}
    for key in MODIFIER_KEYS.get(mod.type, []):
        try:
            val = getattr(mod, key)
            info[key] = list(val) if hasattr(val, "__len__") and not isinstance(val, str) else val
        except Exception:
            pass
    return info


def custom_props(obj):
    out = {}
    for k in obj.keys():
        if k.startswith("_"):
            continue
        try:
            v = obj[k]
            out[k] = v if isinstance(v, (int, float, str, bool)) else str(v)
        except Exception:
            pass
    return out


def mesh_info(obj, depsgraph, materials):
    verts = tris = 0
    try:
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        verts = len(mesh.vertices)
        tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
        eval_obj.to_mesh_clear()
    except Exception:
        pass
    names = []
    for slot in obj.material_slots:
        if slot.material:
            names.append(slot.material.name)
            if slot.material.name not in materials:
                materials[slot.material.name] = material_info(slot.material)
    return {
        "name": obj.name,
        "parent": obj.parent.name if obj.parent else None,
        "collections": [c.name for c in obj.users_collection],
        "dimensions_m": [r(d) for d in obj.dimensions],
        "location": [r(v) for v in obj.location],
        "tris": tris,
        "verts": verts,
        "uv_layers": len(obj.data.uv_layers),
        "modifiers": [modifier_info(m) for m in obj.modifiers],
        "materials": names,
        "custom_props": custom_props(obj),
    }


def empty_info(obj):
    return {
        "name": obj.name,
        "parent": obj.parent.name if obj.parent else None,
        "location": [r(v) for v in obj.location],
        "rotation_deg": [r(v * 57.29578, 2) for v in obj.rotation_euler],
        "scale": [r(v) for v in obj.scale],
        "children": [c.name for c in obj.children],
        "custom_props": custom_props(obj),
    }


def collection_bounds(name, depsgraph):
    col = bpy.data.collections.get(name)
    if col is None:
        return None
    mins = [1e9, 1e9, 1e9]
    maxs = [-1e9, -1e9, -1e9]
    found = False
    for obj in col.all_objects:
        if obj.type != "MESH":
            continue
        try:
            ev = obj.evaluated_get(depsgraph)
            mesh = ev.to_mesh()
            mw = ev.matrix_world
            for v in mesh.vertices:
                p = mw @ v.co
                for i in range(3):
                    mins[i] = min(mins[i], p[i])
                    maxs[i] = max(maxs[i], p[i])
            ev.to_mesh_clear()
            found = True
        except Exception:
            pass
    if not found:
        return None
    return {"min": [r(v) for v in mins], "size_m": [r(maxs[i] - mins[i]) for i in range(3)]}


def skipped(obj):
    return any(c.name in SKIP_COLLECTIONS for c in obj.users_collection)


def main():
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    pool = list(bpy.context.selected_objects if ONLY_SELECTED else scene.objects)
    pool = [o for o in pool if not skipped(o)]
    meshes = [o for o in pool if o.type == "MESH"][:MAX_OBJECTS]
    empties = [o for o in pool if o.type == "EMPTY"]
    materials = {}
    report = {
        "report_version": 2,
        "blender_version": bpy.app.version_string,
        "unit_scale": r(scene.unit_settings.scale_length),
        "reference_bounds": collection_bounds(REF_COLLECTION, depsgraph),
        "object_count": len(meshes),
        "total_tris": 0,
        "objects": [],
        "empties": [empty_info(o) for o in empties],
    }
    for obj in meshes:
        info = mesh_info(obj, depsgraph, materials)
        report["total_tris"] += info["tris"]
        report["objects"].append(info)
    report["materials"] = materials
    report["material_nodes"] = {
        n: node_tree_dump(bpy.data.materials[n])
        for n in DEEP_MATERIALS if n in bpy.data.materials
    }

    text = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    bpy.context.window_manager.clipboard = text
    block = bpy.data.texts.get("style_report.json") or bpy.data.texts.new("style_report.json")
    block.clear()
    block.write(json.dumps(report, ensure_ascii=False, indent=1))
    print("Informe copiado: %d objetos, %d vacios, %d tris, %d caracteres"
          % (report["object_count"], len(empties), report["total_tris"], len(text)))


main()
