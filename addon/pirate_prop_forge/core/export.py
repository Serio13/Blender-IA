"""Paquete de exportacion para Unity: FBX + .blend + texturas PNG + informe JSON."""
import json
from dataclasses import dataclass
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from . import colliders, lods, meshutil, naming, textures
from .errors import PFError
from .settings import COLLIDERS, LAYOUTS

VERSION = "0.1.0"
LOD_SCREEN_HEIGHTS = (0.5, 0.2, 0.08, 0.03)


@dataclass
class ExportOptions:
    formats: tuple = ("fbx", "blend")
    layout: str = "grouped"
    collider: str = "hint"
    col_max_tris: int = colliders.COL_MAX_TRIS
    keep_uv2: bool = True
    verify: bool = False

    def validate(self):
        if self.layout not in LAYOUTS:
            raise PFError("layout '%s' invalido (opciones: %s)" % (self.layout, ", ".join(LAYOUTS)))
        if self.collider not in COLLIDERS:
            raise PFError("collider '%s' invalido (opciones: %s)" % (self.collider, ", ".join(COLLIDERS)))
        bad = [f for f in self.formats if f not in ("fbx", "blend")]
        if bad:
            raise PFError("formato(s) no soportado(s): %s" % ", ".join(bad))


class _Temp:
    """Registro de datablocks temporales para limpiarlos siempre."""

    def __init__(self):
        self.objects, self.meshes, self.materials, self.collections, self.scenes = [], [], [], [], []
        self.held = []

    def claim(self, datablocks, name):
        """Libera `name` renombrando temporalmente al datablock existente (evita sufijos .001)."""
        other = datablocks.get(name)
        if other is not None:
            other.name = name + "__pf_held"
            self.held.append((other, name))

    def cleanup(self):
        for obj in self.objects:
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj)
        for mesh in self.meshes:
            if mesh.name in bpy.data.meshes and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        for mat in self.materials:
            if mat.name in bpy.data.materials and mat.users == 0:
                bpy.data.materials.remove(mat)
        for scene in self.scenes:
            if scene.name in bpy.data.scenes:
                bpy.data.scenes.remove(scene)
        for col in self.collections:
            if col.name in bpy.data.collections:
                bpy.data.collections.remove(col)
        for db, name in self.held:
            try:
                db.name = name
            except ReferenceError:
                pass
        self.held = []


def _unity_name(asset, label, level, with_lod):
    base = asset if not label else "%s_%s" % (asset, naming.safe(label))
    return "%s_LOD%d" % (base, level) if with_lod else base


def _build_hierarchy(asset, levels, opts, tmp, tmp_col):
    """Copias normalizadas (ancla en el origen, escala aplicada) con nodos aptos para Unity."""
    anchor_inv = meshutil.anchor_matrix(asset.anchor).inverted()
    with_lod = len(levels) > 1
    grouped = opts.layout == "grouped" and not asset.single

    def new_empty(name, parent=None):
        tmp.claim(bpy.data.objects, name)
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = "PLAIN_AXES"
        tmp_col.objects.link(obj)
        tmp.objects.append(obj)
        if parent is not None:
            obj.parent = parent
        return obj

    mat_cache = {}

    def unity_material(src, slot):
        if src.name not in mat_cache:
            mat_name = "M_%s" % asset.name if slot == 0 else "M_%s_%d" % (asset.name, slot)
            tmp.claim(bpy.data.materials, mat_name)
            copy = src.copy()
            copy.name = mat_name
            mat_cache[src.name] = copy
            tmp.materials.append(copy)
        return mat_cache[src.name]

    # Sin raiz explicita: Unity crea la raiz con el nombre del FBX. Con el espacio horneado, una malla
    # anidada bajo un vacio que NO es de primer nivel recibe un giro extra de 90 grados.
    out_nodes = {}
    for level in levels:
        lod_parent = new_empty("%s_LOD%d" % (asset.name, level.index)) if (grouped and with_lod) else None
        by_source = {o.get("pf_source", o.name): o for o in level.objects}
        for part in asset.parts:
            src = by_source.get(part.obj.name, part.obj)
            offset = Vector(src.get("pf_offset", (0.0, 0.0, 0.0)))
            world = Matrix.Translation(-offset) @ src.matrix_world
            loc, rot, scl = (anchor_inv @ world).decompose()
            mesh = src.data.copy()
            tmp.meshes.append(mesh)
            if any(abs(c - 1.0) > 1e-6 for c in scl):
                mesh.transform(Matrix.Diagonal(scl).to_4x4())
            if scl.x * scl.y * scl.z < 0:
                mesh.flip_normals()
            for i, m in enumerate(list(mesh.materials)):
                if m is not None:
                    mesh.materials[i] = unity_material(m, i)
            if not opts.keep_uv2:
                lods.drop_extra_uvs(mesh)
            name = _unity_name(asset.name, part.label if not asset.single else "", level.index, with_lod)
            tmp.claim(bpy.data.meshes, name)
            tmp.claim(bpy.data.objects, name)
            mesh.name = name
            obj = bpy.data.objects.new(name, mesh)
            obj.matrix_basis = Matrix.LocRotScale(loc, rot, Vector((1.0, 1.0, 1.0)))
            tmp_col.objects.link(obj)
            tmp.objects.append(obj)
            if lod_parent is not None:
                obj.parent = lod_parent
            out_nodes.setdefault(level.index, []).append(obj)
    bpy.context.view_layer.update()
    return out_nodes


def _lod0_bounds(out_nodes):
    return meshutil.objects_bounds(out_nodes[0])


def _add_collider(asset, out_nodes, opts, tmp, tmp_col):
    lo, hi = _lod0_bounds(out_nodes)
    info = {"hint": colliders.hint_from_bounds(lo, hi), "mesh": None}
    if opts.collider == "mesh":
        pts = [meshutil.world_points(o) for o in out_nodes[0]]
        import numpy as np
        tmp.claim(bpy.data.meshes, asset.name + "_COL")
        mesh = colliders.build_hull_mesh(np.vstack(pts), asset.name + "_COL", opts.col_max_tris)
        tmp.meshes.append(mesh)
        tmp.claim(bpy.data.objects, asset.name + "_COL")
        obj = bpy.data.objects.new(asset.name + "_COL", mesh)
        tmp_col.objects.link(obj)
        tmp.objects.append(obj)
        info["mesh"] = {"object": obj.name, "tris": meshutil.tri_count(mesh)}
        bpy.context.view_layer.update()
    return info


def _fbx(path, collection):
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=False,
        collection=collection.name,
        object_types={"EMPTY", "MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        bake_space_transform=True,
        axis_forward="-Z",
        axis_up="Y",
        mesh_smooth_type="OFF",
        use_mesh_modifiers=True,
        add_leaf_bones=False,
        path_mode="STRIP",
        embed_textures=False,
        bake_anim=False,
    )


def _write_blend(path, asset_name, tmp_col):
    """Guarda la jerarquia como coleccion (para Append). Escribir una Scene cierra Blender."""
    if asset_name not in bpy.data.collections:
        tmp_col.name = asset_name
    bpy.data.libraries.write(str(path), {tmp_col}, fake_user=True, compress=True)


def verify_fbx(path):
    """Reimporta el FBX en la escena actual, lo inspecciona y lo elimina."""
    before_o, before_m, before_i = set(bpy.data.objects), set(bpy.data.meshes), set(bpy.data.images)
    before_mat = set(bpy.data.materials)
    bpy.ops.import_scene.fbx(filepath=str(path))
    new_objs = [o for o in bpy.data.objects if o not in before_o]
    meshes = [o for o in new_objs if o.type == "MESH"]
    bpy.context.view_layer.update()
    lod_meshes = [o for o in meshes if "_LOD" in o.name]
    main = [o for o in lod_meshes if o.name.split("_LOD")[-1].split(".")[0] == "0"] or \
           [o for o in meshes if not o.name.endswith("_COL")]
    info = {
        "nodes": sorted(o.name for o in new_objs),
        "tris": {o.name: meshutil.tri_count(o.data) for o in meshes},
        "bounds": None,
    }
    b = meshutil.objects_bounds(main)
    if b is not None:
        info["bounds"] = {"min": meshutil.r3(b[0]), "max": meshutil.r3(b[1])}
    for o in new_objs:
        bpy.data.objects.remove(o)
    for m in [m for m in bpy.data.meshes if m not in before_m]:
        bpy.data.meshes.remove(m)
    for m in [m for m in bpy.data.materials if m not in before_mat]:
        bpy.data.materials.remove(m)
    for i in [i for i in bpy.data.images if i not in before_i]:
        bpy.data.images.remove(i)
    return info


def export_asset(asset, out_dir, lod_result, opts):
    opts.validate()
    pkg = Path(out_dir) / asset.name
    pkg.mkdir(parents=True, exist_ok=True)
    warnings, notes = [], list(lod_result.notes)

    images, unknown = textures.collect_images([p.obj for p in asset.parts])
    tex_files, tex_warn = [], []
    if images:
        tex_files, tex_warn = textures.write_texture_set(images, pkg / "Textures", asset.name)
    else:
        tex_warn.append("sin texturas reconocidas en los materiales")
    warnings.extend(tex_warn)
    if unknown:
        warnings.append("imagenes sin tipo reconocido (no exportadas): " + ", ".join(sorted(set(unknown))))

    tmp = _Temp()
    tmp_col = bpy.data.collections.new("%s_export" % asset.name)
    tmp.collections.append(tmp_col)
    bpy.context.scene.collection.children.link(tmp_col)
    files, verify = {}, None
    try:
        out_nodes = _build_hierarchy(asset, lod_result.levels, opts, tmp, tmp_col)
        collider = None
        if opts.collider != "none":
            collider = _add_collider(asset, out_nodes, opts, tmp, tmp_col)
        lo, hi = _lod0_bounds(out_nodes)
        if "fbx" in opts.formats:
            fbx_path = pkg / (asset.name + ".fbx")
            _fbx(fbx_path, tmp_col)
            files["fbx"] = fbx_path.name
        if "blend" in opts.formats:
            blend_path = pkg / (asset.name + ".blend")
            _write_blend(blend_path, asset.name, tmp_col)
            files["blend"] = blend_path.name
        uv_layers = max(len(o.data.uv_layers) for o in out_nodes[0])
        node_names = {str(i): [o.name for o in objs] for i, objs in out_nodes.items()}
    finally:
        tmp.cleanup()
    if opts.verify and "fbx" in files:
        verify = verify_fbx(pkg / files["fbx"])

    unity_props = {t["unity_property"]: "Textures/" + t["file"] for t in tex_files}
    report = {
        "tool": "pirate_prop_forge",
        "version": VERSION,
        "asset": asset.name,
        "source_blend": Path(bpy.data.filepath).name if bpy.data.filepath else None,
        "layout": opts.layout,
        "anchor": asset.anchor.name,
        "size_m_blender_xyz": meshutil.r3(hi - lo),
        "uv_layers": uv_layers,
        "lods": [{"level": lv.index, "tris": lv.tris, "verts": lv.verts} for lv in lod_result.levels],
        "nodes": node_names,
        "files": files,
        "textures": tex_files,
        "unity_material": {"shader": "Universal Render Pipeline/Lit", "properties": unity_props},
        "unity_lod_screen_heights": list(LOD_SCREEN_HEIGHTS[: max(0, len(lod_result.levels) - 1)]),
        "collider": collider,
        "notes": notes,
        "warnings": warnings,
    }
    if verify is not None:
        report["verify"] = verify
    (pkg / (asset.name + "_report.json")).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    report["package"] = str(pkg)
    return report
