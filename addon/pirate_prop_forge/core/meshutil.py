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
