"""Generacion de LODs por pieza. LOD0 son los objetos originales y no se modifican."""
from dataclasses import dataclass, field
from math import radians

import bpy
import bmesh  # noqa: E402  (con el modulo bpy, bmesh solo existe tras importar bpy)
import numpy as np
from mathutils import Matrix, Vector

from . import meshutil, naming, quality

LODS_COLLECTION = "PF_LODS"
MIN_PART_TRIS = 8      # una pieza no baja de aqui
COPY_BELOW = 12        # piezas diminutas se copian sin decimar
TOLERANCE = 0.08       # error relativo aceptado sobre el objetivo de una pieza
REDUCTION_GAIN = 0.85  # un LOD debe quedar por debajo de esta fraccion del anterior


@dataclass
class Level:
    index: int
    tris: int
    verts: int
    objects: list = field(default_factory=list)
    quality: dict = None


@dataclass
class LodResult:
    asset: str
    levels: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def tris(self):
        return [lv.tris for lv in self.levels]


def _mesh_totals(objs):
    tris = sum(meshutil.tri_count(o.data) for o in objs)
    verts = sum(len(o.data.vertices) for o in objs)
    return tris, verts


def _lods_collection():
    col = bpy.data.collections.get(LODS_COLLECTION)
    if col is None:
        col = bpy.data.collections.new(LODS_COLLECTION)
        bpy.context.scene.collection.children.link(col)
    elif col.name not in bpy.context.scene.collection.children:
        try:
            bpy.context.scene.collection.children.link(col)
        except RuntimeError:
            pass
    return col


def lod_objects(asset):
    """LODs ya generados para un asset: {nivel: [objetos]}."""
    names = {p.obj.name for p in asset.parts}
    out = {}
    for obj in bpy.data.objects:
        lvl = obj.get("pf_lod")
        if lvl is not None and obj.get("pf_source") in names:
            out.setdefault(int(lvl), []).append(obj)
    return out


def clear_lods(asset):
    removed = 0
    for objs in lod_objects(asset).values():
        for obj in objs:
            mesh = obj.data
            bpy.data.objects.remove(obj)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
            removed += 1
    return removed


def _flat_fraction(mesh):
    attr = mesh.attributes.get("sharp_face")
    if attr is None or len(mesh.polygons) == 0:
        return 0.0
    vals = np.zeros(len(mesh.polygons), dtype=bool)
    attr.data.foreach_get("value", vals)
    return float(vals.mean())


def _apply_shading(mesh, flat, smooth_deg):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if flat:
        for f in bm.faces:
            f.smooth = False
    else:
        limit = radians(smooth_deg)
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            if e.is_manifold and e.calc_face_angle(0.0) > limit:
                e.smooth = False
    bm.to_mesh(mesh)
    bm.free()


def _evaluated_tris(tmp):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = tmp.evaluated_get(dg)
    mesh = ev.to_mesh()
    try:
        return meshutil.tri_count(mesh)
    finally:
        ev.to_mesh_clear()


def make_lod_mesh(src_obj, target_tris, s):
    """Mesh nuevo (sin enlazar a ningun objeto) con ~target_tris triangulos."""
    src_mesh = src_obj.data
    src_tris = meshutil.tri_count(src_mesh)
    tmp = bpy.data.objects.new("_pf_tmp", src_mesh)
    bpy.context.scene.collection.objects.link(tmp)
    try:
        if s.dissolve_deg > 0:
            dis = tmp.modifiers.new("pf_dissolve", "DECIMATE")
            dis.decimate_type = "DISSOLVE"
            dis.angle_limit = radians(s.dissolve_deg)
            dis.delimit = {"UV", "MATERIAL"}
        col = tmp.modifiers.new("pf_collapse", "DECIMATE")
        col.decimate_type = "COLLAPSE"
        col.use_collapse_triangulate = True
        col.ratio = 1.0
        base = _evaluated_tris(tmp)
        ratio = 1.0
        if base > target_tris:
            ratio = max(0.01, min(1.0, target_tris / base))
            for _ in range(4):
                col.ratio = ratio
                got = _evaluated_tris(tmp)
                if abs(got - target_tris) <= TOLERANCE * target_tris:
                    break
                ratio = max(0.01, min(1.0, ratio * target_tris / max(got, 1)))
        dg = bpy.context.evaluated_depsgraph_get()
        mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    finally:
        bpy.data.objects.remove(tmp)
    flat = _flat_fraction(src_mesh) > 0.5
    _apply_shading(mesh, flat, s.smooth_deg)
    if not s.keep_uv2:
        drop_extra_uvs(mesh)
    return mesh


def drop_extra_uvs(mesh):
    while len(mesh.uv_layers) > 1:
        mesh.uv_layers.remove(mesh.uv_layers[-1])


def _level_targets(total0, s):
    """Lista de objetivos totales de triangulos para LOD1.. (ya filtrada)."""
    wanted = list(s.tris) if s.tris else [round(total0 * r) for r in s.ratios]
    kept, notes, prev = [], [], total0
    for i, tgt in enumerate(wanted, start=1):
        if tgt < s.min_tris:
            notes.append("LOD%d omitido: %d tris < min %d" % (i, tgt, s.min_tris))
        elif tgt > prev * REDUCTION_GAIN:
            notes.append("LOD%d omitido: %d tris no reduce lo suficiente" % (i, tgt))
        else:
            kept.append(tgt)
            prev = tgt
    return kept, notes


def generate_lods(asset, s):
    clear_lods(asset)
    originals = [p.obj for p in asset.parts]
    tris0, verts0 = _mesh_totals(originals)
    res = LodResult(asset.name, [Level(0, tris0, verts0, originals)])
    if tris0 < s.skip_below:
        res.notes.append("%d tris < %d: no necesita LODs" % (tris0, s.skip_below))
        return res

    targets, notes = _level_targets(tris0, s)
    res.notes.extend(notes)
    if any(p.obj.modifiers for p in asset.parts):
        res.notes.append("modificadores de los originales ignorados (se usa la malla base)")

    lo, hi = meshutil.objects_bounds(originals)
    width = float(hi[0] - lo[0])
    col = _lods_collection()
    shares = [(p, meshutil.tri_count(p.obj.data)) for p in asset.parts]

    level = 0
    for tgt_total in targets:
        candidate = level + 1
        offset = Vector((candidate * width * 1.25, 0.0, 0.0)) if s.spread else Vector()
        objs, checks = [], []
        for part, part_tris in shares:
            if part_tris <= COPY_BELOW:
                goal = part_tris
            else:
                goal = max(MIN_PART_TRIS, round(tgt_total * part_tris / tris0))
            mesh = make_lod_mesh(part.obj, goal, s)
            checks.append(quality.compare(part.obj.data, mesh))
            stem = naming.strip_baked(part.obj.name)
            mesh.name = "%s_LOD%d" % (stem, candidate)
            obj = bpy.data.objects.new(mesh.name, mesh)
            obj.matrix_world = Matrix.Translation(offset) @ part.obj.matrix_world
            obj["pf_lod"] = candidate
            obj["pf_source"] = part.obj.name
            obj["pf_asset"] = asset.name
            obj["pf_offset"] = list(offset)
            obj["pf_generated"] = True
            col.objects.link(obj)
            objs.append(obj)
        t, v = _mesh_totals(objs)
        prev = res.levels[-1].tris
        if t > prev * REDUCTION_GAIN:
            for obj in objs:
                mesh = obj.data
                bpy.data.objects.remove(obj)
                bpy.data.meshes.remove(mesh)
            res.notes.append("LOD%d omitido: %d tris no mejora los %d del anterior" % (candidate, t, prev))
            continue
        level = candidate
        q = quality.worst(checks)
        res.levels.append(Level(level, t, v, objs, q))
        res.warnings.extend(quality.warnings_for(level, q))
    return res


def existing_levels(asset):
    """Reconstruye un LodResult con LOD0 + LODs ya presentes en la escena (o None)."""
    found = lod_objects(asset)
    if not found:
        return None
    originals = [p.obj for p in asset.parts]
    tris0, verts0 = _mesh_totals(originals)
    res = LodResult(asset.name, [Level(0, tris0, verts0, originals)])
    for lvl in sorted(found):
        t, v = _mesh_totals(found[lvl])
        res.levels.append(Level(lvl, t, v, found[lvl]))
    return res
