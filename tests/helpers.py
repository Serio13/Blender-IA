"""Constructores de assets sinteticos que imitan los _BAKED de produccion."""
from math import radians

import bpy
import bmesh  # noqa: E402  (con el modulo bpy, bmesh solo existe tras importar bpy)
import numpy as np
from mathutils import Vector


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_image(name, size=64, kind="color", packed=True, value=None):
    img = bpy.data.images.new(name, size, size, alpha=True)
    if kind in ("metal", "rough", "normal"):
        img.colorspace_settings.name = "Non-Color"  # antes de los pixeles: despues los pone a cero
    arr = np.zeros((size, size, 4), dtype=np.float32)
    xs = np.linspace(0, 1, size, dtype=np.float32)
    if kind == "metal":
        arr[..., :3] = 0.25 if value is None else value
    elif kind == "rough":
        arr[..., :3] = 0.6 if value is None else value
    elif kind == "normal":
        arr[..., 0], arr[..., 1], arr[..., 2] = 0.5, 0.5, 1.0
    else:
        arr[..., 0] = xs[None, :]
        arr[..., 1] = xs[:, None]
        arr[..., 2] = 0.3
    arr[..., 3] = 1.0
    img.pixels.foreach_set(arr.ravel())
    if packed:
        img.pack()
    return img


def make_material(asset, kinds=("BaseColor", "Normal", "Metallic", "Roughness"), size=64,
                  metal=0.25, rough=0.6, mat_name=None):
    mat = bpy.data.materials.new(mat_name or ("TXB_" + asset))
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    for kind in kinds:
        k = kind.lower()
        mapping = {"basecolor": "color", "emission": "color", "normal": "normal",
                   "metallic": "metal", "roughness": "rough", "metalsmooth": "metal"}
        value = {"metallic": metal, "roughness": rough}.get(k)
        img = make_image("TX_%s_%s" % (asset, kind), size, mapping[k], value=value)
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.label = kind
        if k == "basecolor":
            tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def make_detailed_box(name, dims=(0.7, 0.45, 0.3), loc=(0, 0, 0), cuts=8, bevel=0.015,
                      uv_layers=2, material=None, parent=None, flat=False, origin_offset=(0, 0, 0)):
    """Caja con bisel y subdivisiones: muchos triangulos y caras planas (estilo dura)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * dims[0], v.co.y * dims[1], v.co.z * dims[2])) - Vector(origin_offset)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=3, affect="EDGES")
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bm.normal_update()
    for i in range(uv_layers):
        layer = bm.loops.layers.uv.new("UVMap" if i == 0 else "UV%d" % (i + 1))
        for f in bm.faces:
            n = f.normal
            axis = max(range(3), key=lambda a: abs(n[a]))
            keep = [a for a in range(3) if a != axis]
            for loop in f.loops:
                loop[layer].uv = (loop.vert.co[keep[0]] / max(dims) + 0.5,
                                  loop.vert.co[keep[1]] / max(dims) + 0.5)
    for f in bm.faces:
        f.smooth = not flat
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if material is not None:
        mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    return obj


def make_barrel(name, loc=(0, 0, 0), segs=48, rings=40, uv_layers=1, material=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=0.3)
    for v in bm.verts:
        v.co.z *= 1.3
    bm.normal_update()
    for i in range(uv_layers):
        layer = bm.loops.layers.uv.new("UVMap" if i == 0 else "UV%d" % (i + 1))
        for f in bm.faces:
            for loop in f.loops:
                loop[layer].uv = (loop.vert.co.x + 0.5, loop.vert.co.z / 0.8 + 0.5)
    for f in bm.faces:
        f.smooth = True
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if material is not None:
        mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    return obj


def make_chest(prefix="Cofre_test", loc=(5.0, 3.0, 0.0), suffix="_BAKED", cuts=8):
    """Cofre de dos piezas (base + tapa con pivote en la bisagra), sin padre."""
    mat = make_material(prefix)
    base = make_detailed_box("%s_base%s" % (prefix, suffix), (0.72, 0.48, 0.30), loc, cuts=cuts,
                             material=mat, origin_offset=(0, 0, -0.15))
    # la tapa tiene su origen en la bisagra (borde trasero superior de la base)
    hinge = (loc[0], loc[1] + 0.24, loc[2] + 0.30)
    lid = make_detailed_box("%s_tapa%s" % (prefix, suffix), (0.70, 0.46, 0.25), hinge, cuts=cuts,
                            material=mat, origin_offset=(0, -0.23, -0.125))
    return base, lid, mat
