"""Control de calidad objetivo de un LOD frente a su original, sin capturas.

Para cada triangulo del LOD se toma su centroide, se busca el punto mas cercano del original (solo entre caras
que miran al mismo lado, para no confundir las dos paredes de una tabla fina) y se mide:
  - dev:   distancia a la superficie original (relativa a la diagonal de la caja del original)
  - uv:    diferencia entre la UV del LOD y la UV interpolada del original en ese punto
  - color: diferencia de COLOR real entre la textura leida con la UV del LOD y con la UV esperada.
           Es lo que se ve: un desplazamiento de UV sobre una zona lisa no cambia el color y no se avisa.
"""
import bpy
import bmesh  # noqa: E402  (con el modulo bpy, bmesh solo existe tras importar bpy)
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

from . import meshutil, textures

MAX_SAMPLES = 4000
MAX_TEXTURE_SIDE = 512   # la textura se submuestrea a esto para comparar (basta para medir color)
UV_WARN = 0.02           # sin textura: p95 de error UV por encima de esto = el mapeo se desplaza
COLOR_WARN = 0.10        # con textura: p95 de diferencia de color (0..1) por encima de esto = se ve distinto
DEV_WARN = 0.012         # p95 de desviacion de forma por encima de esto: el LOD se aleja del original
SAME_SIDE = 0.3          # producto escalar minimo entre normales para aceptar la cara cercana
SEARCH_RADIUS = 0.01     # radio de busqueda de caras candidatas (fraccion de la diagonal)


def _pct(values, q):
    return float(np.percentile(values, q)) if len(values) else 0.0


def load_basemap(obj):
    """Pixeles RGB (h, w, 3) de la textura BaseMap del objeto, submuestreados, o None."""
    images, _unknown = textures.collect_images([obj])
    img = images.get("BaseMap")
    if img is None or img.size[0] == 0 or img.size[1] == 0:
        return None
    pixels = textures._read(img)[..., :3]
    step = max(1, max(pixels.shape[:2]) // MAX_TEXTURE_SIDE)
    return pixels[::step, ::step]


def _uv_layer(bm, mesh, preferred):
    """Capa UV de bmesh que usan las texturas: la nombrada, la de render o la primera."""
    if len(mesh.uv_layers) == 0:
        return None
    name = mesh.uv_layers[meshutil.render_uv_index(mesh, preferred)].name
    return bm.loops.layers.uv.get(name)


def _nearest_same_side(bvh, point, normal, radius):
    """Punto mas cercano del original entre las caras que miran hacia el mismo lado."""
    best = None
    for loc, n, idx, dist in bvh.find_nearest_range(point, radius):
        if n.dot(normal) > SAME_SIDE and (best is None or dist < best[3]):
            best = (loc, n, idx, dist)
    return best if best is not None else bvh.find_nearest(point)


def compare(ref_mesh, lod_mesh, uv_name=None, texture=None):
    """Compara dos meshes en el mismo espacio local.

    Devuelve dev_p95, dev_max, uv_p95, uv_mean (None sin UV) y color_p95, color_mean (None sin textura).
    """
    ref, lod = bmesh.new(), bmesh.new()
    empty = {"dev_p95": 0.0, "dev_max": 0.0, "uv_p95": None, "uv_mean": None,
             "color_p95": None, "color_mean": None}
    try:
        ref.from_mesh(ref_mesh)
        lod.from_mesh(lod_mesh)
        ref.faces.ensure_lookup_table()
        ref.normal_update()
        lod.normal_update()
        lod_tris = lod.calc_loop_triangles()
        if not ref.faces or not lod_tris:
            return empty
        bvh = BVHTree.FromBMesh(ref)
        ref_uv = _uv_layer(ref, ref_mesh, uv_name)
        lod_uv = _uv_layer(lod, lod_mesh, uv_name)
        coords = np.array([v.co[:] for v in ref.verts])
        diag = float(np.linalg.norm(coords.max(axis=0) - coords.min(axis=0))) or 1.0
        radius = SEARCH_RADIUS * diag
        use_color = texture is not None and ref_uv is not None and lod_uv is not None
        if use_color:
            th, tw = texture.shape[:2]

            def texel(uv):
                return texture[int((uv[1] % 1.0) * th) % th, int((uv[0] % 1.0) * tw) % tw]

        step = max(1, len(lod_tris) // MAX_SAMPLES)
        devs, uv_errs, color_errs = [], [], []
        for tri in lod_tris[::step]:
            p = (tri[0].vert.co + tri[1].vert.co + tri[2].vert.co) / 3.0
            normal = tri[0].face.normal
            hit = _nearest_same_side(bvh, p, normal, radius)
            loc, _n, idx, dist = hit
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
                if use_color:
                    color_errs.append(float(np.abs(texel(expected) - texel(got)).max()))
        return {
            "dev_p95": round(_pct(devs, 95), 5),
            "dev_max": round(max(devs) if devs else 0.0, 5),
            "uv_p95": round(_pct(uv_errs, 95), 5) if uv_errs else None,
            "uv_mean": round(float(np.mean(uv_errs)), 5) if uv_errs else None,
            "color_p95": round(_pct(color_errs, 95), 5) if color_errs else None,
            "color_mean": round(float(np.mean(color_errs)), 5) if color_errs else None,
        }
    finally:
        ref.free()
        lod.free()


def worst(results):
    """Agrega resultados de varias piezas quedandose con el peor valor de cada metrica."""
    out = {"dev_p95": 0.0, "dev_max": 0.0, "uv_p95": None, "uv_mean": None,
           "color_p95": None, "color_mean": None}
    for r in results:
        out["dev_p95"] = max(out["dev_p95"], r["dev_p95"])
        out["dev_max"] = max(out["dev_max"], r["dev_max"])
        for k in ("uv_p95", "uv_mean", "color_p95", "color_mean"):
            v = r.get(k)
            if v is not None:
                out[k] = v if out[k] is None else max(out[k], v)
    return out


def warnings_for(level, q):
    msgs = []
    color = q.get("color_p95")
    if color is not None:
        if color > COLOR_WARN:
            msgs.append("LOD%d: la textura se ve distinta (diferencia de color p95 %.0f%%)" % (level, color * 100))
    elif q["uv_p95"] is not None and q["uv_p95"] > UV_WARN:
        msgs.append("LOD%d: el mapeo de textura se desplaza (UV p95 %.1f%%)" % (level, q["uv_p95"] * 100))
    if q["dev_p95"] > DEV_WARN:
        msgs.append("LOD%d: la forma se aleja del original (p95 %.1f%% de la diagonal)" % (level, q["dev_p95"] * 100))
    return msgs
