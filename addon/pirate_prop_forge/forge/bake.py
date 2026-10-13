"""Horneado de los materiales procedurales a texturas (Cycles en CPU) y material unico `_BAKED`."""
import bpy
import numpy as np

from . import palette

PASSES = (
    # (tipo de imagen, tipo de bake, srgb)
    ("BaseColor", "DIFFUSE", True),
    ("Roughness", "ROUGHNESS", False),
    ("Normal", "NORMAL", False),
)


def _new_image(name, size, srgb, fill=(0.0, 0.0, 0.0, 1.0)):
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, size, size, alpha=True)
    img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    img.alpha_mode = "CHANNEL_PACKED"
    img.pixels.foreach_set(np.tile(np.array(fill, np.float32), size * size))
    return img


def _bake_pass(obj, mats, bake_type, image, margin, samples):
    """Hornea `bake_type` de todos los materiales de `obj` sobre `image`."""
    nodes_added = []
    for mat in mats:
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        mat.node_tree.nodes.active = node
        nodes_added.append((mat, node))
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.render.bake.margin = margin
    scene.render.bake.margin_type = "EXTEND"
    scene.render.bake.use_clear = True
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    kwargs = {"type": bake_type, "margin": margin, "use_clear": True}
    if bake_type == "DIFFUSE":
        kwargs["pass_filter"] = {"COLOR"}
    bpy.ops.object.bake(**kwargs)
    for mat, node in nodes_added:
        mat.node_tree.nodes.remove(node)


def bake_object(obj, asset, size=1024, samples=8, margin=6, collection=None):
    """Devuelve un nuevo objeto `<obj>_BAKED` con UN material y texturas TX_<asset>_<Tipo> empaquetadas."""
    # copia de trabajo con materiales propios (el bake anade nodos temporales)
    work = obj.copy()
    work.data = obj.data.copy()
    (collection or bpy.context.scene.collection).objects.link(work)
    work_mats = []
    for i, m in enumerate(list(work.data.materials)):
        copy = m.copy()
        work.data.materials[i] = copy
        work_mats.append(copy)
    images = {}
    try:
        for kind, bake_type, srgb in PASSES:
            fill = (0.5, 0.5, 1.0, 1.0) if kind == "Normal" else (0.0, 0.0, 0.0, 1.0)
            img = _new_image("TX_%s_%s" % (asset, kind), size, srgb, fill)
            _bake_pass(work, work_mats, bake_type, img, margin, samples)
            images[kind] = img
        metal = _new_image("TX_%s_Metallic" % asset, size, False, (0.0, 0.0, 0.0, 1.0))
        images["Metallic"] = metal
    finally:
        for m in work_mats:
            bpy.data.materials.remove(m)
    # material unico
    mat = bpy.data.materials.new("TXB_%s" % asset)
    tree, links = mat.node_tree, mat.node_tree.links
    bsdf = tree.nodes["Principled BSDF"]
    for k, (kind, img) in enumerate(images.items()):
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image, node.label = img, kind
        node.location = (-700, 300 - 260 * k)
        if kind == "BaseColor":
            links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        elif kind == "Roughness":
            links.new(node.outputs["Color"], bsdf.inputs["Roughness"])
        elif kind == "Metallic":
            links.new(node.outputs["Color"], bsdf.inputs["Metallic"])
        elif kind == "Normal":
            nm = tree.nodes.new("ShaderNodeNormalMap")
            nm.location = (-400, 0)
            links.new(node.outputs["Color"], nm.inputs["Color"])
            links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        img.pack()
    me = work.data
    me.materials.clear()
    me.materials.append(mat)
    for poly in me.polygons:
        poly.material_index = 0
    return work, images
