"""Materiales procedurales por rol (madera con veta y variacion por tabla, hierro martillado, tela, cuerda, oro)
y materiales planos para ver la geometria. Los patrones usan coordenadas UV de tamano real (densidad conocida)
para que la veta siga el largo de cada pieza y el tamano del detalle sea el mismo en todo el asset."""
import bpy

from . import palette


# --------------------------------------------------------------------------------------------------------------
# materiales planos
# --------------------------------------------------------------------------------------------------------------
def solid(role, name=None):
    name = name or "PF_" + role
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    r, g, b = palette.role_color(role)
    bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
    bsdf.inputs["Roughness"].default_value = palette.role_rough(role)
    bsdf.inputs["Metallic"].default_value = palette.role_metal(role)
    mat.diffuse_color = (r, g, b, 1.0)
    return mat


# --------------------------------------------------------------------------------------------------------------
# ayudante de nodos
# --------------------------------------------------------------------------------------------------------------
class Nodes:
    def __init__(self, mat):
        self.mat = mat
        self.tree = mat.node_tree
        self.links = self.tree.links
        self.n = self.tree.nodes
        self.x = -1000
        self.y = 0

    def add(self, kind, **props):
        node = self.n.new(kind)
        for k, v in props.items():
            setattr(node, k, v)
        node.location = (self.x, self.y)
        self.y -= 180
        return node

    def link(self, out, inp):
        self.links.new(out, inp)

    def set(self, sock, value):
        if hasattr(value, "links") or hasattr(value, "node"):      # es un socket de salida
            self.links.new(value, sock)
        else:
            if isinstance(value, (tuple, list)) and len(value) == 3 and sock.type == "RGBA":
                value = (*value, 1.0)
            sock.default_value = value

    def coord(self):
        return self.add("ShaderNodeTexCoord")

    def mapping(self, vec, scale=(1, 1, 1), loc=(0, 0, 0)):
        m = self.add("ShaderNodeMapping")
        self.link(vec, m.inputs["Vector"])
        m.inputs["Scale"].default_value = scale
        m.inputs["Location"].default_value = loc
        return m

    def noise(self, vec, scale, detail=2.0, rough=0.5, distortion=0.0):
        t = self.add("ShaderNodeTexNoise", noise_dimensions="3D")
        self.link(vec, t.inputs["Vector"])
        t.inputs["Scale"].default_value = scale
        t.inputs["Detail"].default_value = detail
        t.inputs["Roughness"].default_value = rough
        t.inputs["Distortion"].default_value = distortion
        return t.outputs["Fac"]

    def voronoi(self, vec, scale, feature="F1", out="Distance", rand=1.0):
        t = self.add("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature=feature)
        self.link(vec, t.inputs["Vector"])
        t.inputs["Scale"].default_value = scale
        t.inputs["Randomness"].default_value = rand
        return t.outputs[out]

    def math(self, op, a, b=None, clamp=False):
        m = self.add("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(m.inputs[0], a)
        if b is not None:
            self.set(m.inputs[1], b)
        return m.outputs[0]

    def mix(self, a, b, fac=0.5, blend="MIX"):
        m = self.add("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self.set(m.inputs[0], fac)
        self.set(m.inputs[6], a)
        self.set(m.inputs[7], b)
        return m.outputs[2]

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
        self.link(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    def attribute(self, name):
        a = self.add("ShaderNodeAttribute", attribute_name=name, attribute_type="GEOMETRY")
        return a.outputs["Fac"]

    def ao(self, distance=0.02, inside=False):
        a = self.add("ShaderNodeAmbientOcclusion", inside=inside, only_local=True, samples=8)
        a.inputs["Distance"].default_value = distance
        return a.outputs["AO"]

    def bump(self, height, strength=0.3, distance=0.01):
        b = self.add("ShaderNodeBump")
        self.set(b.inputs["Height"], height)
        b.inputs["Strength"].default_value = strength
        b.inputs["Distance"].default_value = distance
        return b.outputs["Normal"]

    def principled(self, color, rough, normal=None, metallic=0.0):
        p = self.n.get("Principled BSDF") or self.add("ShaderNodeBsdfPrincipled")
        self.set(p.inputs["Base Color"], color)
        self.set(p.inputs["Roughness"], rough)
        p.inputs["Metallic"].default_value = metallic
        if normal is not None:
            self.link(normal, p.inputs["Normal"])
        return p


def _scale(density, across_m, along_m):
    """Escala de ruido en UV para que el detalle mida across_m (ancho) x along_m (largo) metros reales."""
    return (1.0 / (across_m * density), 1.0 / (along_m * density), 1.0)


def _tint(color, k):
    return tuple(max(0.0, min(1.0, c * k)) for c in color)


# --------------------------------------------------------------------------------------------------------------
# materiales procedurales
# --------------------------------------------------------------------------------------------------------------
def _wood(nd, role, density, wear):
    base = palette.role_color(role)
    uv = nd.coord().outputs["UV"]
    grain_map = nd.mapping(uv, _scale(density, 0.0035, 0.06))
    fine_map = nd.mapping(uv, _scale(density, 0.0012, 0.02))
    wide_map = nd.mapping(uv, _scale(density, 0.04, 0.35))
    grain = nd.noise(grain_map.outputs["Vector"], 1.0, detail=6.0, rough=0.62, distortion=0.6)
    fine = nd.noise(fine_map.outputs["Vector"], 1.0, detail=2.0, rough=0.5)
    blotch = nd.noise(wide_map.outputs["Vector"], 1.0, detail=3.0, rough=0.5)

    # tono por tabla (pf_id) y hue ligeramente variable
    pid = nd.attribute("pf_id")
    tone = nd.ramp(pid, [(0.0, _tint(base, 0.78)), (0.5, base), (1.0, _tint((base[0] * 1.12, base[1] * 1.03, base[2] * 0.85), 1.30))])
    streak = nd.ramp(grain, [(0.30, (0.62, 0.60, 0.58)), (0.55, (0.95, 0.93, 0.9)), (0.8, (1.12, 1.1, 1.06))])
    color = nd.mix(tone, streak, 1.0, "MULTIPLY")
    color = nd.mix(color, nd.ramp(blotch, [(0.35, (0.78, 0.76, 0.74)), (0.65, (1.08, 1.06, 1.04))]), 0.55, "MULTIPLY")
    # grietas finas: lineas donde la distancia al borde de voronoi es pequena, solo en zonas sueltas
    crack_map = nd.mapping(uv, _scale(density, 0.05, 0.16))
    edge = nd.voronoi(crack_map.outputs["Vector"], 1.0, feature="DISTANCE_TO_EDGE", out="Distance")
    mask = nd.math("LESS_THAN", edge, 0.011)
    where = nd.math("GREATER_THAN", nd.noise(wide_map.outputs["Vector"], 1.7, detail=2.0), 0.70 - 0.2 * wear)
    cracks = nd.math("MULTIPLY", mask, where)
    color = nd.mix(color, (0.05, 0.03, 0.015), nd.math("MULTIPLY", cracks, 0.45 + 0.3 * wear), "MIX")
    # oscurecimiento en juntas y bordes
    occl = nd.ao(0.018)
    color = nd.mix(color, _tint(base, 0.35), nd.math("SUBTRACT", 1.0, occl, clamp=True), "MULTIPLY")
    rough = nd.math("ADD", palette.role_rough(role) - 0.08, nd.math("MULTIPLY", fine, 0.22))
    nrm = nd.bump(nd.math("ADD", nd.math("MULTIPLY", grain, 0.7), nd.math("MULTIPLY", fine, 0.3)), 0.7, 0.006)
    return nd.principled(color, rough, nrm)


def _hammered(nd, role, density, wear):
    base = palette.role_color(role)
    obj = nd.coord().outputs["UV"]
    big = nd.mapping(obj, _scale(density, 0.02, 0.02))
    small = nd.mapping(obj, _scale(density, 0.006, 0.006))
    dents = nd.voronoi(big.outputs["Vector"], 1.0, feature="F1", out="Distance")
    grit = nd.noise(small.outputs["Vector"], 1.0, detail=4.0, rough=0.6)
    tone = nd.ramp(dents, [(0.0, (1.18, 1.18, 1.2)), (0.5, (1.0, 1.0, 1.0)), (1.0, (0.78, 0.78, 0.82))])
    color = nd.mix(_tint(base, 0.62), tone, 1.0, "MULTIPLY")
    color = nd.mix(color, nd.ramp(grit, [(0.3, (0.82, 0.82, 0.85)), (0.7, (1.1, 1.1, 1.12))]), 0.6, "MULTIPLY")
    occl = nd.ao(0.012)
    color = nd.mix(color, _tint(base, 0.4), nd.math("SUBTRACT", 1.0, occl, clamp=True), "MULTIPLY")
    rough = nd.math("ADD", palette.role_rough(role) - 0.1, nd.math("MULTIPLY", grit, 0.25))
    nrm = nd.bump(nd.math("ADD", nd.math("MULTIPLY", dents, 0.9), nd.math("MULTIPLY", grit, 0.15)), 0.9, 0.006)
    return nd.principled(color, rough, nrm)


def _gold(nd, role, density, wear):
    base = palette.role_color(role)
    uv = nd.coord().outputs["UV"]
    m = nd.mapping(uv, _scale(density, 0.01, 0.01))
    n = nd.noise(m.outputs["Vector"], 1.0, detail=3.0)
    color = nd.mix(base, nd.ramp(n, [(0.3, (0.85, 0.8, 0.7)), (0.7, (1.1, 1.05, 1.0))]), 0.7, "MULTIPLY")
    occl = nd.ao(0.01)
    color = nd.mix(color, _tint(base, 0.4), nd.math("SUBTRACT", 1.0, occl, clamp=True), "MULTIPLY")
    return nd.principled(color, palette.role_rough(role), nd.bump(n, 0.15, 0.002))


def _cloth(nd, role, density, wear):
    base = palette.role_color(role)
    uv = nd.coord().outputs["UV"]
    weave_a = nd.mapping(uv, _scale(density, 0.004, 0.004))
    weave_b = nd.mapping(uv, _scale(density, 0.004, 0.004), loc=(0.37, 0.11, 0))
    wide = nd.mapping(uv, _scale(density, 0.05, 0.05))
    pattern = nd.math("ADD", nd.voronoi(weave_a.outputs["Vector"], 1.0, "F1", "Distance"),
                      nd.voronoi(weave_b.outputs["Vector"], 1.0, "F1", "Distance"))
    blotch = nd.noise(wide.outputs["Vector"], 1.0, detail=4.0)
    color = nd.mix(base, nd.ramp(pattern, [(0.2, (1.12, 1.1, 1.1)), (0.9, (0.78, 0.76, 0.76))]), 0.8, "MULTIPLY")
    color = nd.mix(color, nd.ramp(blotch, [(0.3, (0.8, 0.8, 0.8)), (0.7, (1.08, 1.08, 1.08))]), 0.7, "MULTIPLY")
    occl = nd.ao(0.012)
    color = nd.mix(color, _tint(base, 0.4), nd.math("SUBTRACT", 1.0, occl, clamp=True), "MULTIPLY")
    return nd.principled(color, 0.78, nd.bump(pattern, 0.5, 0.002))


def _rope(nd, role, density, wear):
    base = palette.role_color(role)
    uv = nd.coord().outputs["UV"]
    twist = nd.mapping(uv, _scale(density, 0.006, 0.012))
    n = nd.noise(twist.outputs["Vector"], 1.0, detail=2.0, rough=0.4, distortion=1.5)
    wave = nd.math("PINGPONG", nd.math("MULTIPLY", nd.math("ADD", n, nd.attribute("pf_id")), 9.0), 1.0)
    color = nd.mix(base, nd.ramp(wave, [(0.2, (0.7, 0.68, 0.62)), (0.8, (1.15, 1.12, 1.05))]), 1.0, "MULTIPLY")
    return nd.principled(color, 0.8, nd.bump(wave, 0.6, 0.002))


_BUILDERS = {}
for r in palette.WOODS:
    _BUILDERS[r] = _wood
for r in ("iron", "iron_light", "copper"):
    _BUILDERS[r] = _hammered
_BUILDERS["gold"] = _gold
for r in palette.CLOTHS:
    _BUILDERS[r] = _cloth
_BUILDERS["rope"] = _rope


def procedural(role, density, wear=0.5, owner="asset"):
    """Material procedural del rol, propio del asset `owner` (si no hay constructor, plano de la paleta)."""
    builder = _BUILDERS.get(role)
    if builder is None:
        return solid(role)
    mat = bpy.data.materials.new("PF_%s_%s" % (owner, role))
    nd = Nodes(mat)
    bsdf = builder(nd, role, density, wear)
    out = mat.node_tree.nodes.get("Material Output")
    nd.link(bsdf.outputs["BSDF"], out.inputs["Surface"])
    r, g, b = palette.role_color(role)
    mat.diffuse_color = (r, g, b, 1.0)
    return mat
