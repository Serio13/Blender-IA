"""Colision sugerida (solo datos) y malla de colision convexa opcional (_COL)."""
from math import radians

import bpy
import bmesh  # noqa: E402  (con el modulo bpy, bmesh solo existe tras importar bpy)
import numpy as np

from . import meshutil

COL_MAX_TRIS = 48


def hint_from_bounds(lo, hi):
    """Caja (y capsula si es alta y esbelta) para colliders de Unity.

    center_blender va en ejes de Blender (seguro). Los valores *_unity asumen la correspondencia
    habitual (x, z, y) = (ancho, alto, fondo); en el centro el signo de Z depende de la importacion,
    asi que revisalo en tu proyecto si el pivote no esta centrado.
    """
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    center = (lo + hi) / 2.0
    size = hi - lo
    to_unity = lambda v: [round(float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]
    box = {"center_blender": [round(float(c), 4) for c in center],
           "center_unity": to_unity(center),
           "size_unity": [abs(x) for x in to_unity(size)]}
    out = {"box": box}
    width = max(size[0], size[1])
    if size[2] >= 1.4 * width and width > 0:
        out["capsule"] = {"center_unity": to_unity(center), "radius": round(float(width / 2), 4),
                          "height": round(float(size[2]), 4), "direction": "Y"}
    return out


def build_hull_mesh(points, name, max_tris=COL_MAX_TRIS):
    """Casco convexo simplificado de un array (n, 3) de puntos; devuelve un Mesh nuevo."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    junk = {g for g in res.get("geom_interior", []) + res.get("geom_unused", [])
            if isinstance(g, bmesh.types.BMVert) and g.is_valid}
    if junk:
        bmesh.ops.delete(bm, geom=list(junk), context="VERTS")

    def tris():
        return sum(len(f.verts) - 2 for f in bm.faces)

    for deg in (5, 10, 15, 25, 35, 50):
        if tris() <= max_tris:
            break
        bmesh.ops.dissolve_limit(bm, angle_limit=radians(deg), verts=bm.verts[:], edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh
