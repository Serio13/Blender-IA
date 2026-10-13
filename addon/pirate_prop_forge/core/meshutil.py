import numpy as np
from mathutils import Matrix, Vector


def tri_count(mesh):
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def world_points(obj):
    """Vertices del mesh en coordenadas de mundo como array (n, 3)."""
    mesh = obj.data
    n = len(mesh.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(n, 3).astype(np.float64)
    m = np.array(obj.matrix_world, dtype=np.float64)
    return co @ m[:3, :3].T + m[:3, 3]


def bounds(points):
    """(min, max) de un array (n, 3)."""
    return points.min(axis=0), points.max(axis=0)


def objects_bounds(objs):
    pts = [world_points(o) for o in objs if len(o.data.vertices)]
    if not pts:
        return None
    lo, hi = bounds(np.vstack(pts))
    return lo, hi


def r3(values, n=4):
    return [round(float(v), n) for v in values]


def anchor_matrix(anchor):
    """Traslacion + rotacion del ancla en el mundo (sin escala)."""
    loc, rot, _scale = anchor.matrix_world.decompose()
    return Matrix.LocRotScale(loc, rot, Vector((1.0, 1.0, 1.0)))


def render_uv_index(mesh, preferred=None):
    """Indice de la capa UV que usan las texturas: la nombrada (nodo UV Map) o, si no, la de render."""
    layers = mesh.uv_layers
    if preferred is not None:
        for i, layer in enumerate(layers):
            if layer.name == preferred:
                return i
    for i, layer in enumerate(layers):
        if layer.active_render:
            return i
    return 0


def order_uv_layers(mesh, preferred=None, keep_extra=True):
    """Pone PRIMERA la capa UV que usan las texturas. Unity usa siempre la primera capa del FBX.

    Blender muestra bien la textura porque usa la capa de render, aunque no sea la primera; en Unity eso se
    ve como un mosaico. Devuelve el nombre de la capa que queda primera (None si no hay capas UV).
    """
    layers = mesh.uv_layers
    count = len(layers)
    if count == 0:
        return None
    idx = render_uv_index(mesh, preferred)
    if idx == 0 and (keep_extra or count == 1):
        layers[0].active_render = True
        return layers[0].name
    stored = []
    size = len(mesh.loops) * 2
    for layer in layers:
        arr = np.empty(size, dtype=np.float32)
        layer.data.foreach_get("uv", arr)
        stored.append((layer.name, arr))
    order = [idx] + [i for i in range(count) if i != idx]
    if not keep_extra:
        order = order[:1]
    while len(layers):
        layers.remove(layers[0])
    for i in order:
        new = layers.new(name=stored[i][0])
        new.data.foreach_set("uv", stored[i][1])
    layers[0].active_render = True
    layers.active_index = 0
    return layers[0].name
