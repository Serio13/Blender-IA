"""Perfil de estilo compacto de la escena (para que un LLM no tenga que leer informes enormes)."""
import json
import statistics
from collections import Counter

import bpy

from . import assets, lods, meshutil, naming, textures

REF_COLLECTION = "REF_pirata"
MAX_FAMILIES = 40


def _in_collection(obj, name):
    return any(c.name == name for c in obj.users_collection)


def build_profile(ref_collection=REF_COLLECTION, max_families=MAX_FAMILIES):
    objs = [o for o in bpy.data.objects
            if assets.is_candidate(o) and not _in_collection(o, ref_collection)
            and not _in_collection(o, lods.LODS_COLLECTION)]
    profile = {
        "unit_scale": round(bpy.context.scene.unit_settings.scale_length, 4),
        "blender": bpy.app.version_string,
        "assets": 0,
        "families": {},
    }
    ref = bpy.data.collections.get(ref_collection)
    if ref is not None:
        b = meshutil.objects_bounds([o for o in ref.all_objects if o.type == "MESH"])
        if b is not None:
            profile["ref_height_m"] = round(float(b[1][2] - b[0][2]), 3)
    if not objs:
        return profile

    fams = {}
    labels = Counter()
    for asset in assets.build_assets(objs):
        tris = sum(meshutil.tri_count(p.obj.data) for p in asset.parts)
        images, _ = textures.collect_images([p.obj for p in asset.parts])
        sizes = sorted({max(img.size) for img in images.values()})
        entry = fams.setdefault(naming.family(asset.name), {"tris": [], "baked": 0, "tex": set(), "uv": set()})
        entry["tris"].append(tris)
        entry["baked"] += int(any(naming.is_baked(p.obj.name) for p in asset.parts))
        entry["tex"].update(sizes)
        entry["uv"].update(len(p.obj.data.uv_layers) for p in asset.parts)
        labels.update(p.label for p in asset.parts if p.label)
        profile["assets"] += 1

    ordered = sorted(fams.items(), key=lambda kv: -len(kv[1]["tris"]))
    for name, e in ordered[:max_families]:
        t = e["tris"]
        profile["families"][name] = {
            "n": len(t), "tris": [min(t), int(statistics.median(t)), max(t)],
            "baked": e["baked"], "tex_px": sorted(e["tex"]), "uv": sorted(e["uv"]),
        }
    if len(ordered) > max_families:
        profile["families_omitted"] = len(ordered) - max_families
    profile["part_labels"] = [k for k, _ in labels.most_common(8)]
    return profile


def summarize(profile):
    lines = ["assets=%d unit_scale=%s%s" % (
        profile["assets"], profile["unit_scale"],
        " ref_h=%sm" % profile["ref_height_m"] if "ref_height_m" in profile else "")]
    for name, f in profile["families"].items():
        lines.append("%s n=%d tris=%d/%d/%d baked=%d tex=%s uv=%s" % (
            name, f["n"], f["tris"][0], f["tris"][1], f["tris"][2], f["baked"],
            "+".join(str(x) for x in f["tex_px"]) or "-", "+".join(str(x) for x in f["uv"])))
    if profile.get("part_labels"):
        lines.append("partes: " + ",".join(profile["part_labels"]))
    return "\n".join(lines)


def write_profile(profile, path):
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return path
