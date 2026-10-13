"""Resolucion de objetivos y agrupacion de piezas en assets."""
import fnmatch
from dataclasses import dataclass, field

import bpy

from . import naming
from .errors import PFError

SKIP_PREFIXES = ("UCX_", "UBX_", "UCP_", "USP_")
ANCHOR_LABELS = ("base", "malla", "")


@dataclass
class Part:
    obj: object
    label: str = ""


@dataclass
class Asset:
    name: str
    parts: list = field(default_factory=list)
    anchor: object = None

    @property
    def single(self):
        return len(self.parts) == 1


def is_candidate(obj):
    if obj.type != "MESH":
        return False
    if obj.get("pf_generated") or obj.get("pf_lod") is not None:
        return False
    if obj.name.startswith(SKIP_PREFIXES) or naming.strip_dup(obj.name).endswith("_COL"):
        return False
    return True


def _meshes_from(obj):
    if obj.type == "MESH":
        return [obj]
    return [c for c in obj.children_recursive if c.type == "MESH"]


def resolve_targets(target=None):
    """target: None (seleccion), nombre de objeto/coleccion, patron con * o ?, o lista."""
    found = []
    if target is None:
        for obj in bpy.context.selected_objects:
            found.extend(_meshes_from(obj))
    else:
        items = [target] if isinstance(target, str) else list(target)
        for item in items:
            if any(ch in item for ch in "*?["):
                found.extend(o for o in bpy.data.objects
                             if o.type == "MESH" and fnmatch.fnmatch(o.name, item))
            elif item in bpy.data.collections:
                found.extend(o for o in bpy.data.collections[item].all_objects if o.type == "MESH")
            elif item in bpy.data.objects:
                found.extend(_meshes_from(bpy.data.objects[item]))
            else:
                raise PFError("no existe objeto ni coleccion '%s'" % item)
    seen, objs = set(), []
    for o in found:
        if o.name not in seen and is_candidate(o):
            seen.add(o.name)
            objs.append(o)
    if not objs:
        raise PFError("sin objetivos validos: selecciona mallas o indica target")
    return objs


def build_assets(objs, name=None, labels=naming.PART_LABELS):
    # Si existe la version _BAKED de una pieza, se ignora la version sin hornear.
    baked_stems = {naming.strip_baked(o.name) for o in objs if naming.is_baked(o.name)}
    objs = [o for o in objs if naming.is_baked(o.name) or naming.strip_baked(o.name) not in baked_stems]

    groups = {}
    for obj in objs:
        asset_name, label = naming.classify(obj, labels)
        groups.setdefault(asset_name, []).append(Part(obj, label))
    if name:
        if len(groups) > 1:
            raise PFError("'name' solo vale para un asset, pero hay %d: %s"
                          % (len(groups), ", ".join(sorted(groups))))
        groups = {name: next(iter(groups.values()))}

    assets = []
    for asset_name in sorted(groups):
        parts = sorted(groups[asset_name], key=lambda p: (p.label not in ANCHOR_LABELS, p.label))
        parents = {p.obj.parent for p in parts}
        if len(parents) == 1 and next(iter(parents)) is not None and next(iter(parents)).type == "EMPTY":
            anchor = next(iter(parents))
        else:
            anchor = parts[0].obj
        assets.append(Asset(naming.safe(asset_name), parts, anchor))
    return assets


def find_assets(target=None, name=None):
    return build_assets(resolve_targets(target), name=name)
