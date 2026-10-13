"""Control de calidad objetivo de un LOD frente a su original, sin capturas.

Para cada triangulo del LOD se toma su centroide, se busca el punto mas cercano en el original y se mide:
  - dev: distancia a la superficie original (relativa a la diagonal de la caja del original)
  - uv:  diferencia entre la UV del LOD y la UV interpolada del original en ese punto (0..1 = textura entera)
"""
import bpy
import bmesh  # noqa: E402  (con el modulo bpy, bmesh solo existe tras importar bpy)
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

from . import meshutil

MAX_SAMPLES = 4000
UV_WARN = 0.02    # p95 de error UV por encima de esto: el mapeo de textura se desplaza
DEV_WARN = 0.012  # p95 de desviacion de forma por encima de esto: el LOD se aleja del original


def _pct(values, q):
    return float(np.percentile(values, q)) if len(values) else 0.0


def _uv_layer(bm, mesh, preferred):
    """Capa UV de bmesh que usan las texturas: la nombrada, la de render o la primera."""
    if len(mesh.uv_layers) == 0:
        return None
    name = mesh.uv_layers[meshutil.render_uv_index(mesh, preferred)].name
    return bm.loops.layers.uv.get(name)


def compare(ref_mesh, lod_mesh, uv_name=None):
    """Compara dos meshes en el mismo espacio local. Devuelve dev_p95, dev_max, uv_p95, uv_mean (o uv None)."""
    ref, lod = bmesh.new(), bmesh.new()
    try:
        ref.from_mesh(ref_mesh)
        lod.from_mesh(lod_mesh)
        ref.faces.ensure_lookup_table()
        ref_tris = ref.calc_loop_triangles()
        lod_tris = lod.calc_loop_triangles()
        if not ref_tris or not lod_tris:
            return {"dev_p95": 0.0, "dev_max": 0.0, "uv_p95": None, "uv_mean": None}
        bvh = BVHTree.FromBMesh(ref)
        ref_uv = _uv_layer(ref, ref_mesh, uv_name)
        lod_uv = _uv_layer(lod, lod_mesh, uv_name)
        coords = np.array([v.co[:] for v in ref.verts])
        diag = float(np.linalg.norm(coords.max(axis=0) - coords.min(axis=0))) or 1.0
        step = max(1, len(lod_tris) // MAX_SAMPLES)
        devs, uv_errs = [], []
        for tri in lod_tris[::step]:
            p = (tri[0].vert.co + tri[1].vert.co + tri[2].vert.co) / 3.0
            loc, _normal, idx, dist = bvh.find_nearest(p)
            if loc is None:
                continue
            devs.append(dist / diag)
            if ref_uv is not None and lod_uv is not None:
                face_loops = list(ref.faces[idx].loops)  # el indice del BVH es de cara
                w = poly_3d_calc([l.vert.co for l in face_loops], loc)
                expected = Vector((0.0, 0.0))
                for l, wi in zip(face_loops, w):
                    expected += l[ref_uv].uv * wi
                got = (tri[0][lod_uv].uv + tri[1][lod_uv].uv + tri[2][lod_uv].uv) / 3.0
                uv_errs.append((expected - got).length)
        return {
            "dev_p95": round(_pct(devs, 95), 5),
            "dev_max": round(max(devs) if devs else 0.0, 5),
            "uv_p95": round(_pct(uv_errs, 95), 5) if uv_errs else None,
            "uv_mean": round(float(np.mean(uv_errs)), 5) if uv_errs else None,
        }
    finally:
        ref.free()
        lod.free()


def worst(results):
    """Agrega resultados de varias piezas quedandose con el peor valor de cada metrica."""
    out = {"dev_p95": 0.0, "dev_max": 0.0, "uv_p95": None, "uv_mean": None}
    for r in results:
        out["dev_p95"] = max(out["dev_p95"], r["dev_p95"])
        out["dev_max"] = max(out["dev_max"], r["dev_max"])
        for k in ("uv_p95", "uv_mean"):
            if r[k] is not None:
                out[k] = r[k] if out[k] is None else max(out[k], r[k])
    return out


def warnings_for(level, q):
    msgs = []
    if q["uv_p95"] is not None and q["uv_p95"] > UV_WARN:
        msgs.append("LOD%d: el mapeo de textura se desplaza (UV p95 %.1f%%)" % (level, q["uv_p95"] * 100))
    if q["dev_p95"] > DEV_WARN:
        msgs.append("LOD%d: la forma se aleja del original (p95 %.1f%% de la diagonal)" % (level, q["dev_p95"] * 100))
    return msgs
