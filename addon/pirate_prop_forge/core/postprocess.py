"""Normalizacion de una malla generada por IA (pilares 2 y 3): importar, limpiar, escala real, pivote,
presupuesto de triangulos y material PBR. Produce un asset `<Nombre>_malla_BAKED` listo para LODs/exportacion.
"""
from dataclasses import dataclass
from pathlib import Path

import bpy
import bmesh
import numpy as np

from . import lods, meshutil, naming, pbr
from .errors import PFError
from .settings import lod_settings

# categoria: (altura real en metros, maximo de triangulos en modo automatico, minimo recomendado)
CATEGORIES = {
    "barril": (0.85, 9000, 800),
    "cofre": (0.55, 10000, 800),
    "caja": (0.50, 6000, 400),
    "llave": (0.14, 5000, 200),
    "cantimplora": (0.20, 6000, 300),
    "botella": (0.30, 5000, 300),
    "personalizado": (None, 10000, 300),
}
PIVOTS = ("base", "center", "keep")
BUDGETS = ("auto", "manual", "off")


@dataclass
class Options:
    category: str = "personalizado"
    height: float = 0.0                 # metros; 0 = el de la categoria (o sin escalar si no hay)
    pivot: str = "base"
    budget: str = "auto"
    min_tris: int = 0                   # solo "manual"
    max_tris: int = 0                   # solo "manual"
    material: str = "ia"                # ia | madera | cuero | metal | none
    tex_size: int = 1024
    smooth: int = 2                     # pasadas de suavizado que conserva el volumen (0 = ninguna); quita la grumosidad de la IA
    drop_islands: float = 0.01          # se descartan fragmentos con menos de este % de las caras del mayor
    color: tuple = None                 # color base opcional para los materiales procedurales

    def validate(self):
        if self.category not in CATEGORIES:
            raise PFError("categoria desconocida '%s' (opciones: %s)" % (self.category, ", ".join(CATEGORIES)))
        if self.pivot not in PIVOTS:
            raise PFError("origen desconocido '%s' (opciones: %s)" % (self.pivot, ", ".join(PIVOTS)))
        if self.budget not in BUDGETS:
            raise PFError("presupuesto desconocido '%s' (opciones: %s)" % (self.budget, ", ".join(BUDGETS)))
        if self.material not in pbr.SOURCES + ("none",):
            raise PFError("material desconocido '%s' (opciones: %s)" % (self.material, ", ".join(pbr.SOURCES + ("none",))))
        if self.budget == "manual":
            if self.max_tris <= 0 or self.min_tris < 0 or self.min_tris > self.max_tris:
                raise PFError("presupuesto manual: hace falta 0 <= minimo <= maximo y maximo > 0")
        if not 0 <= self.smooth <= 10:
            raise PFError("suavizado: de 0 a 10 pasadas")
        if self.tex_size not in (128, 256, 512, 1024, 2048):
            raise PFError("tamaño de textura no valido: %s" % self.tex_size)
        return self


# --------------------------------------------------------------------------------------------------------------
# importar
# --------------------------------------------------------------------------------------------------------------
def import_mesh(path):
    """Importa OBJ/GLB/GLTF y devuelve UN objeto malla (varias piezas se unen) en coordenadas de mundo."""
    path = str(path)
    if not Path(path).is_file():
        raise PFError("no existe el archivo: %s" % path)
    before = set(bpy.data.objects)
    ext = Path(path).suffix.lower()
    if ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext in (".glb", ".gltf"):
        try:
            bpy.ops.import_scene.gltf(filepath=path)
        except AttributeError:
            bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
            bpy.ops.import_scene.gltf(filepath=path)
    else:
        raise PFError("formato no soportado: %s (usa .obj, .glb o .gltf)" % ext)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        for o in new:
            bpy.data.objects.remove(o)
        raise PFError("el archivo no contiene mallas: %s" % path)
    for o in meshes:                                  # fuera de jerarquias, conservando la posicion
        world = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = world
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    mesh = obj.data
    mesh.transform(obj.matrix_world)
    obj.matrix_world.identity()
    return obj


# --------------------------------------------------------------------------------------------------------------
# limpieza
# --------------------------------------------------------------------------------------------------------------
def _components(bm):
    """Lista de listas de caras conectadas por aristas."""
    seen, comps = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, comp = [f], []
        seen.add(f.index)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb.index not in seen:
                        seen.add(nb.index)
                        stack.append(nb)
        comps.append(comp)
    return comps


def clean(obj, drop_islands=0.01):
    """Une vertices duplicados, borra sueltos y fragmentos minusculos, recalcula normales hacia fuera.

    Devuelve un dict con lo que se quito.
    """
    mesh = obj.data
    n0v, n0f = len(mesh.vertices), len(mesh.polygons)
    pts = meshutil.world_points(obj)
    diag = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) if len(pts) else 1.0
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=max(1e-7, diag * 1e-5))
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=max(1e-8, diag * 1e-7))
    bm.faces.ensure_lookup_table()
    dropped = 0
    if drop_islands > 0 and len(bm.faces):
        bm.faces.index_update()
        comps = _components(bm)
        biggest = max(len(c) for c in comps)
        kill = [f for c in comps if len(c) < max(2, drop_islands * biggest) for f in c]
        if kill and len(kill) < len(bm.faces):
            bmesh.ops.delete(bm, geom=kill, context="FACES")
            dropped = len(kill)
    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose_v = [v for v in bm.verts if not v.link_faces]
    if loose_v:
        bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return {"verts_removed": n0v - len(mesh.vertices), "faces_removed": n0f - len(mesh.polygons),
            "fragment_faces": dropped, "loose": len(loose_v) + len(loose_e)}


def smooth(obj, iterations=2, lam=0.5, mu=-0.53):
    """Suavizado de Taubin (alterna encoger y expandir): quita la grumosidad sin reducir el volumen."""
    mesh = obj.data
    n, ne = len(mesh.vertices), len(mesh.edges)
    if iterations <= 0 or n == 0 or ne == 0:
        return
    co = np.empty(n * 3, np.float32)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(n, 3).astype(np.float64)
    ev = np.empty(ne * 2, np.int32)
    mesh.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    deg = np.bincount(ev.ravel(), minlength=n).astype(np.float64)
    deg[deg == 0] = 1.0
    for _ in range(iterations):
        for factor in (lam, mu):
            acc = np.zeros_like(co)
            np.add.at(acc, ev[:, 0], co[ev[:, 1]])
            np.add.at(acc, ev[:, 1], co[ev[:, 0]])
            co += factor * (acc / deg[:, None] - co)
    mesh.vertices.foreach_set("co", co.astype(np.float32).ravel())
    mesh.update()


# --------------------------------------------------------------------------------------------------------------
# escala y pivote
# --------------------------------------------------------------------------------------------------------------
def normalize(obj, height=0.0, pivot="base"):
    """Escala a `height` metros de alto (0 = no escalar) y coloca el origen. Aplica todo en los vertices."""
    mesh = obj.data
    n = len(mesh.vertices)
    if n == 0:
        raise PFError("la malla esta vacia")
    co = np.empty(n * 3, np.float32)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(n, 3).astype(np.float64)
    lo, hi = co.min(axis=0), co.max(axis=0)
    size_z = float(hi[2] - lo[2])
    if size_z <= 1e-9:
        raise PFError("la malla no tiene altura")
    scale = (height / size_z) if height and height > 0 else 1.0
    if pivot == "base":
        origin = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    elif pivot == "center":
        origin = (lo + hi) / 2
    else:
        origin = np.zeros(3)
    co = (co - origin) * scale
    mesh.vertices.foreach_set("co", co.astype(np.float32).ravel())
    mesh.update()
    obj.location, obj.rotation_euler, obj.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    return scale, (hi - lo) * scale


# --------------------------------------------------------------------------------------------------------------
# presupuesto de triangulos
# --------------------------------------------------------------------------------------------------------------
def apply_budget(obj, opts):
    """Reduce al maximo del presupuesto (UV y sombreado conservados). Devuelve (tris_antes, tris_despues, aviso)."""
    mesh = obj.data
    before = meshutil.tri_count(mesh)
    if opts.budget == "off":
        lods._apply_shading(mesh, False, 35.0)
        return before, before, None
    if opts.budget == "manual":
        lo, hi = opts.min_tris, opts.max_tris
    else:
        _h, hi, lo = CATEGORIES[opts.category]
    warning = None
    after = before
    if before > hi:
        new = lods.make_lod_mesh(obj, hi, lod_settings(strict=False, smooth_deg=35.0))
        new.name = mesh.name
        old = obj.data
        obj.data = new
        bpy.data.meshes.remove(old)
        after = meshutil.tri_count(new)
    else:
        lods._apply_shading(mesh, False, 35.0)
    if after < lo:
        warning = "malla con %d triangulos, bajo el minimo %d (puede faltar detalle)" % (after, lo)
    return before, after, warning


# --------------------------------------------------------------------------------------------------------------
# entrada principal
# --------------------------------------------------------------------------------------------------------------
def process(path, name, opts=None):
    """Malla cruda de la IA -> asset `<name>_malla_BAKED`. Devuelve (objeto, informe dict)."""
    opts = (opts or Options()).validate()
    asset = naming.safe(name)
    if not asset:
        raise PFError("falta el nombre del asset")
    obj = import_mesh(path)
    notes, warnings = [], []
    try:
        raw_tris = meshutil.tri_count(obj.data)
        stats = clean(obj, opts.drop_islands)
        smooth(obj, opts.smooth)
        height = opts.height or CATEGORIES[opts.category][0] or 0.0
        scale, dims = normalize(obj, height, opts.pivot)
        before, after, warn = apply_budget(obj, opts)
        if warn:
            warnings.append(warn)
        mat_name = None
        if opts.material != "none":
            mat_name, mat_notes = _apply_material(obj, asset, opts)
            notes += mat_notes
        obj.name = "%s_malla%s" % (asset, naming.BAKED_SUFFIX)
        obj.data.name = obj.name
        obj["pf_ai"] = True
    except Exception:
        bpy.data.objects.remove(obj)
        raise
    report = {
        "object": obj.name, "asset": asset, "raw_tris": raw_tris, "tris": after, "reduced_from": before,
        "size_m": [round(float(d), 3) for d in dims], "scale": round(float(scale), 4), "cleaned": stats,
        "material": mat_name, "warnings": warnings, "notes": notes,
    }
    return obj, report


def _apply_material(obj, asset, opts):
    notes = []
    if opts.material == "ia":
        has_tex = any(s.material and s.material.node_tree and any(n.type == "TEX_IMAGE" for n in s.material.node_tree.nodes)
                      for s in obj.material_slots)
        if has_tex:
            mat, notes = pbr.adopt_ai_textures(obj, asset)
        elif len(obj.data.color_attributes):
            mat, made_uv = pbr.bake_vertex_colors(obj, asset, opts.tex_size)
            notes.append("color por vertice horneado a textura" + (" (UV nuevas)" if made_uv else ""))
        else:
            raise PFError("material 'ia': la malla no trae texturas ni color; elige madera, cuero o metal")
    else:
        mat, made_uv = pbr.bake_procedural(obj, asset, opts.material, opts.tex_size, color=opts.color)
        if made_uv:
            notes.append("UV generadas")
    return mat.name, notes


def summary(report):
    line = "%s: %d tris (IA %d) alto %.2f m, %s" % (
        report["object"], report["tris"], report["raw_tris"], report["size_m"][2], "mat=" + (report["material"] or "ninguno"))
    c = report["cleaned"]
    if c["verts_removed"] or c["fragment_faces"]:
        line += " limpieza: -%d vert, -%d caras de fragmentos" % (c["verts_removed"], c["fragment_faces"])
    if report["warnings"]:
        line += " AVISO: " + "; ".join(report["warnings"])
    return line
