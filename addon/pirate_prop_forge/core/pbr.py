"""Materiales PBR para mallas generadas por IA (pilar 4).

Tres vias, todas terminan en UN material `TXB_<asset>` con imagenes empaquetadas `TX_<asset>_<Tipo>`:
  - "ia":       conserva las texturas que trae la malla (SF3D: color, normal, rugosidad, metal) renombradas;
                si solo hay color por vertice (TripoSR) lo hornea a textura.
  - "madera" / "cuero" / "metal": material procedural por coordenadas de objeto (en metros, la malla ya esta
                normalizada) horneado a BaseColor + Roughness + Normal (Cycles en CPU).
"""
import math

import bpy
import numpy as np

from .errors import PFError

PRESETS = {
    # nombre: (color base lineal, rugosidad, metalico)
    "madera": ((0.32, 0.191, 0.094), 0.55, 0.0),
    "cuero": ((0.17, 0.085, 0.045), 0.68, 0.0),
    "metal": ((0.20, 0.22, 0.25), 0.42, 0.85),
}
SOURCES = ("ia",) + tuple(PRESETS)
KINDS = ("BaseColor", "Roughness", "Normal", "Metallic")


# --------------------------------------------------------------------------------------------------------------
# imagenes
# --------------------------------------------------------------------------------------------------------------
def new_image(name, size, srgb, fill=(0.0, 0.0, 0.0, 1.0), height=None):
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    w, h = size, (height or size)
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"      # antes de rellenar los pixeles
    img.alpha_mode = "CHANNEL_PACKED"
    img.pixels.foreach_set(np.tile(np.array(fill, np.float32), w * h))
    return img


def _read(img):
    w, h = img.size
    arr = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(arr)
    return arr.reshape(h, w, 4)


def _write(name, arr, srgb):
    h, w = arr.shape[:2]
    img = new_image(name, w, srgb, height=h)
    out = np.ascontiguousarray(arr, dtype=np.float32)
    img.pixels.foreach_set(out.ravel())
    return img


# --------------------------------------------------------------------------------------------------------------
# UV
# --------------------------------------------------------------------------------------------------------------
def ensure_uv(obj, angle_deg=66.0, margin=0.004):
    """Si la malla no tiene UV, la desenvuelve (proyeccion inteligente). Devuelve True si la creo."""
    mesh = obj.data
    if len(mesh.uv_layers):
        return False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle_deg), island_margin=margin)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    if len(mesh.uv_layers):
        mesh.uv_layers[0].name = "UVMap"
    return True


# --------------------------------------------------------------------------------------------------------------
# materiales procedurales (coordenadas de objeto = metros)
# --------------------------------------------------------------------------------------------------------------
class _Nodes:
    def __init__(self, mat):
        self.tree, self.links, self.n = mat.node_tree, mat.node_tree.links, mat.node_tree.nodes
        self.y = 0

    def add(self, kind, **props):
        node = self.n.new(kind)
        for k, v in props.items():
            setattr(node, k, v)
        node.location = (-900, self.y)
        self.y -= 200
        return node

    def put(self, sock, value):
        if hasattr(value, "node"):
            self.links.new(value, sock)
        else:
            if isinstance(value, (tuple, list)) and len(value) == 3 and sock.type == "RGBA":
                value = (*value, 1.0)
            sock.default_value = value

    def mapping(self, scale):
        coord = self.add("ShaderNodeTexCoord")
        m = self.add("ShaderNodeMapping")
        self.links.new(coord.outputs["Object"], m.inputs["Vector"])
        m.inputs["Scale"].default_value = scale
        return m.outputs["Vector"]

    def noise(self, vec, detail=4.0, rough=0.55, distortion=0.0):
        t = self.add("ShaderNodeTexNoise", noise_dimensions="3D")
        self.links.new(vec, t.inputs["Vector"])
        t.inputs["Scale"].default_value = 1.0
        t.inputs["Detail"].default_value = detail
        t.inputs["Roughness"].default_value = rough
        t.inputs["Distortion"].default_value = distortion
        return t.outputs["Fac"]

    def voronoi(self, vec, feature="F1", out="Distance"):
        t = self.add("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature=feature)
        self.links.new(vec, t.inputs["Vector"])
        t.inputs["Scale"].default_value = 1.0
        return t.outputs[out]

    def ramp(self, fac, stops):
        r = self.add("ShaderNodeValToRGB")
        ramp = r.color_ramp
        while len(ramp.elements) > len(stops):
            ramp.elements.remove(ramp.elements[-1])
        while len(ramp.elements) < len(stops):
            ramp.elements.new(0.5)
        for el, (pos, col) in zip(ramp.elements, stops):
            el.position = pos
            el.color = (*col[:3], 1.0)
        self.links.new(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    def math(self, op, a, b=None, clamp=False):
        m = self.add("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.put(m.inputs[0], a)
        if b is not None:
            self.put(m.inputs[1], b)
        return m.outputs[0]

    def mix(self, a, b, fac, blend="MULTIPLY"):
        m = self.add("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self.put(m.inputs[0], fac)
        self.put(m.inputs[6], a)
        self.put(m.inputs[7], b)
        return m.outputs[2]

    def ao(self, distance):
        a = self.add("ShaderNodeAmbientOcclusion", only_local=True, samples=8)
        a.inputs["Distance"].default_value = distance
        return a.outputs["AO"]

    def bump(self, height, strength, distance):
        b = self.add("ShaderNodeBump")
        self.put(b.inputs["Height"], height)
        b.inputs["Strength"].default_value = strength
        b.inputs["Distance"].default_value = distance
        return b.outputs["Normal"]


def _tint(c, k):
    return tuple(max(0.0, min(1.0, v * k)) for v in c)


def _darken_cavities(nd, color, base, dist):
    occl = nd.ao(dist)
    return nd.mix(color, _tint(base, 0.45), nd.math("SUBTRACT", 1.0, occl, clamp=True))


def _wood(nd, base, rough):
    grain = nd.noise(nd.mapping((55.0, 55.0, 5.0)), detail=6.0, rough=0.62, distortion=0.6)
    fine = nd.noise(nd.mapping((180.0, 180.0, 18.0)), detail=2.0)
    stave = nd.voronoi(nd.mapping((7.0, 7.0, 0.9)), feature="F1", out="Color")
    tone = nd.mix(base, stave, 0.22, "MULTIPLY")
    streak = nd.ramp(grain, [(0.30, (0.62, 0.60, 0.58)), (0.55, (0.95, 0.93, 0.90)), (0.80, (1.12, 1.10, 1.06))])
    color = nd.mix(tone, streak, 1.0)
    seam = nd.voronoi(nd.mapping((7.0, 7.0, 0.9)), feature="DISTANCE_TO_EDGE", out="Distance")
    color = nd.mix(color, (0.04, 0.025, 0.012), nd.math("LESS_THAN", seam, 0.025), "MIX")
    color = _darken_cavities(nd, color, base, 0.02)
    r = nd.math("ADD", rough - 0.08, nd.math("MULTIPLY", fine, 0.22))
    n = nd.bump(nd.math("ADD", nd.math("MULTIPLY", grain, 0.7), nd.math("MULTIPLY", fine, 0.3)), 0.7, 0.006)
    return color, r, n


def _leather(nd, base, rough):
    cells = nd.voronoi(nd.mapping((95.0, 95.0, 95.0)), feature="F1", out="Distance")
    blotch = nd.noise(nd.mapping((9.0, 9.0, 9.0)), detail=4.0)
    wear = nd.noise(nd.mapping((22.0, 22.0, 22.0)), detail=3.0)
    color = nd.mix(base, nd.ramp(cells, [(0.0, (1.15, 1.13, 1.12)), (0.6, (0.92, 0.9, 0.9)), (1.0, (0.7, 0.68, 0.68))]), 1.0)
    color = nd.mix(color, nd.ramp(blotch, [(0.3, (0.78, 0.76, 0.75)), (0.7, (1.12, 1.10, 1.08))]), 0.8)
    color = _darken_cavities(nd, color, base, 0.015)
    r = nd.math("ADD", rough - 0.1, nd.math("MULTIPLY", wear, 0.25))
    n = nd.bump(nd.math("MULTIPLY", cells, 1.0), 0.45, 0.003)
    return color, r, n


def _metal(nd, base, rough):
    dents = nd.voronoi(nd.mapping((38.0, 38.0, 38.0)), feature="F1", out="Distance")
    grit = nd.noise(nd.mapping((160.0, 160.0, 160.0)), detail=4.0, rough=0.6)
    rust = nd.noise(nd.mapping((14.0, 14.0, 14.0)), detail=4.0)
    tone = nd.ramp(dents, [(0.0, (1.18, 1.18, 1.2)), (0.5, (1.0, 1.0, 1.0)), (1.0, (0.78, 0.78, 0.82))])
    color = nd.mix(_tint(base, 0.8), tone, 1.0)
    color = nd.mix(color, nd.ramp(grit, [(0.3, (0.82, 0.82, 0.85)), (0.7, (1.1, 1.1, 1.12))]), 0.6)
    rust_mask = nd.math("GREATER_THAN", rust, 0.66)
    color = nd.mix(color, (0.2, 0.075, 0.03), nd.math("MULTIPLY", rust_mask, 0.55), "MIX")
    color = _darken_cavities(nd, color, base, 0.012)
    r = nd.math("ADD", rough - 0.1, nd.math("MULTIPLY", grit, 0.28))
    n = nd.bump(nd.math("ADD", nd.math("MULTIPLY", dents, 0.9), nd.math("MULTIPLY", grit, 0.15)), 0.8, 0.005)
    return color, r, n


_BUILD = {"madera": _wood, "cuero": _leather, "metal": _metal}


def procedural_material(preset, owner, color=None):
    """Material de trabajo (solo para hornear) del preset, con coordenadas de objeto."""
    if preset not in PRESETS:
        raise PFError("material desconocido '%s' (opciones: %s)" % (preset, ", ".join(SOURCES)))
    base, rough, metallic = PRESETS[preset]
    if color is not None:
        base = tuple(float(c) for c in color[:3])
    mat = bpy.data.materials.new("PFTMP_%s_%s" % (owner, preset))
    nd = _Nodes(mat)
    col, r, n = _BUILD[preset](nd, base, rough)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    mat.node_tree.links.new(col, bsdf.inputs["Base Color"])
    mat.node_tree.links.new(r, bsdf.inputs["Roughness"])
    mat.node_tree.links.new(n, bsdf.inputs["Normal"])
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


# --------------------------------------------------------------------------------------------------------------
# horneado
# --------------------------------------------------------------------------------------------------------------
def _bake(obj, mat, bake_type, image, margin, samples):
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    mat.node_tree.nodes.active = node
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    kw = {"type": bake_type, "margin": margin, "margin_type": "EXTEND", "use_clear": True}
    if bake_type == "DIFFUSE":
        kw["pass_filter"] = {"COLOR"}
    try:
        bpy.ops.object.bake(**kw)
    finally:
        mat.node_tree.nodes.remove(node)


def _assign_single(obj, mat):
    me = obj.data
    me.materials.clear()
    me.materials.append(mat)
    for poly in me.polygons:
        poly.material_index = 0


def assemble_material(asset, images):
    """Material unico `TXB_<asset>` con las imagenes {tipo: imagen} (empaquetadas)."""
    old = bpy.data.materials.get("TXB_%s" % asset)
    if old is not None:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new("TXB_%s" % asset)
    tree, links = mat.node_tree, mat.node_tree.links
    bsdf = tree.nodes["Principled BSDF"]
    for k, kind in enumerate(KINDS):
        img = images[kind]
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
    return mat


def bake_procedural(obj, asset, preset, size=1024, samples=24, margin=8, color=None):
    """Aplica el preset procedural y lo hornea a texturas TX_<asset>_*. Devuelve el material final."""
    made_uv = ensure_uv(obj)
    tmp = procedural_material(preset, asset, color)
    _assign_single(obj, tmp)
    images = {}
    try:
        for kind, bake_type, srgb, fill in (("BaseColor", "DIFFUSE", True, (0, 0, 0, 1)),
                                            ("Roughness", "ROUGHNESS", False, (0.5, 0.5, 0.5, 1)),
                                            ("Normal", "NORMAL", False, (0.5, 0.5, 1.0, 1))):
            img = new_image("TX_%s_%s" % (asset, kind), size, srgb, fill)
            _bake(obj, tmp, bake_type, img, margin, samples)
            images[kind] = img
        m = PRESETS[preset][2]
        images["Metallic"] = new_image("TX_%s_Metallic" % asset, size, False, (m, m, m, 1.0))
        mat = assemble_material(asset, images)
    finally:
        bpy.data.materials.remove(tmp)
    _assign_single(obj, mat)
    return mat, made_uv


def bake_vertex_colors(obj, asset, size=1024, samples=4, margin=8):
    """Malla con solo color por vertice (TripoSR): se desenvuelve y se hornea a BaseColor."""
    me = obj.data
    if not len(me.color_attributes):
        raise PFError("la malla no trae color por vertice ni texturas")
    attr = me.color_attributes[0].name
    made_uv = ensure_uv(obj)
    tmp = bpy.data.materials.new("PFTMP_%s_vcol" % asset)
    tree = tmp.node_tree
    emit = tree.nodes.new("ShaderNodeEmission")
    vc = tree.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = attr
    tree.links.new(vc.outputs["Color"], emit.inputs["Color"])
    tree.links.new(emit.outputs["Emission"], tree.nodes["Material Output"].inputs["Surface"])
    _assign_single(obj, tmp)
    images = {}
    try:
        base = new_image("TX_%s_BaseColor" % asset, size, True)
        _bake(obj, tmp, "EMIT", base, margin, samples)
        images["BaseColor"] = base
        images["Roughness"] = new_image("TX_%s_Roughness" % asset, size, False, (0.7, 0.7, 0.7, 1.0))
        images["Normal"] = new_image("TX_%s_Normal" % asset, size, False, (0.5, 0.5, 1.0, 1.0))
        images["Metallic"] = new_image("TX_%s_Metallic" % asset, size, False, (0.0, 0.0, 0.0, 1.0))
        mat = assemble_material(asset, images)
    finally:
        bpy.data.materials.remove(tmp)
    _assign_single(obj, mat)
    return mat, made_uv


# --------------------------------------------------------------------------------------------------------------
# texturas que trae la IA (glTF) -> TX_<asset>_*
# --------------------------------------------------------------------------------------------------------------
_CHANNEL = {"Red": 0, "R": 0, "Green": 1, "G": 1, "Blue": 2, "B": 2}


def _trace(sock, channel=None, depth=0):
    """Sigue un socket hacia atras hasta un nodo de imagen. Devuelve (nodo_imagen, canal) o None."""
    if depth > 8 or not sock.is_linked:
        return None
    link = sock.links[0]
    node = link.from_node
    if node.type == "TEX_IMAGE":
        return (node, channel) if node.image is not None else None
    if node.type in ("SEPARATE_COLOR", "SEPARATE_RGB"):
        return _trace(node.inputs[0], _CHANNEL.get(link.from_socket.name, channel), depth + 1)
    for inp in node.inputs:                       # normal map, mezclas, matematicas...
        if inp.is_linked:
            found = _trace(inp, channel, depth + 1)
            if found:
                return found
    return None


def _first_principled(obj):
    for slot in obj.material_slots:
        mat = slot.material
        if mat and mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    return n
    return None


def adopt_ai_textures(obj, asset, size=None):
    """Convierte el material de la malla de la IA en `TXB_<asset>` con TX_<asset>_<Tipo> empaquetadas.

    Devuelve (material, notas). Lo que falte se rellena con valores neutros y se indica en las notas.
    """
    bsdf = _first_principled(obj)
    if bsdf is None:
        raise PFError("la malla no trae material con texturas")
    notes, images = [], {}

    def pixels(kind):
        found = _trace(bsdf.inputs[kind])
        if found is None:
            return None
        node, ch = found
        return _read(node.image), ch

    # color
    got = pixels("Base Color")
    if got:
        arr, _ = got
        arr = arr.copy()
        arr[..., 3] = 1.0
        images["BaseColor"] = _write("TX_%s_BaseColor" % asset, arr, True)
    else:
        c = tuple(bsdf.inputs["Base Color"].default_value)
        images["BaseColor"] = new_image("TX_%s_BaseColor" % asset, size or 512, True, (*c[:3], 1.0))
        notes.append("sin textura de color")
    h, w = images["BaseColor"].size[1], images["BaseColor"].size[0]

    for kind, sock_name, default in (("Roughness", "Roughness", 0.7), ("Metallic", "Metallic", 0.0)):
        got = pixels(sock_name)
        if got:
            arr, ch = got
            plane = arr[..., ch if ch is not None else 0]
            out = np.stack([plane, plane, plane, np.ones_like(plane)], axis=-1)
            images[kind] = _write("TX_%s_%s" % (asset, kind), out, False)
        else:
            v = float(bsdf.inputs[sock_name].default_value)
            images[kind] = new_image("TX_%s_%s" % (asset, kind), w, False, (v, v, v, 1.0), height=h)
            if kind == "Roughness" and v == default:
                notes.append("sin mapa de rugosidad")

    got = pixels("Normal")
    if got:
        arr = got[0].copy()
        arr[..., 3] = 1.0
        images["Normal"] = _write("TX_%s_Normal" % asset, arr, False)
    else:
        images["Normal"] = new_image("TX_%s_Normal" % asset, w, False, (0.5, 0.5, 1.0, 1.0), height=h)
        notes.append("sin mapa normal")

    old_mats = [s.material for s in obj.material_slots if s.material]
    mat = assemble_material(asset, images)
    _assign_single(obj, mat)
    for m in old_mats:
        if m.users == 0:
            bpy.data.materials.remove(m)
    for img in list(bpy.data.images):
        if img.users == 0 and not img.name.startswith("TX_"):
            bpy.data.images.remove(img)
    return mat, notes
