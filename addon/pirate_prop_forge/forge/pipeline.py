"""De una spec a un asset listo para el resto de la tuberia (LODs / exportacion)."""
from math import radians

import bpy

from . import bake, build, generators

FAMILY = {"barrel": "Barril", "chest": "Cofre", "crate": "Caja", "key": "Llave"}


def asset_name(spec):
    """Barril_polvora, Cofre_raro...; el sufijo _V2 marca la version premium (como en el proyecto)."""
    family = FAMILY.get(spec["archetype"], spec["archetype"].capitalize())
    variant = spec.get("variant")
    return "%s_%s" % (family, variant) if variant else family


def make_asset(spec, size=1024, samples=8, do_bake=True, keep_procedural=True, collection=None, location=(0, 0, 0)):
    """Crea `<Asset>_V2_*` (procedural) y `<Asset>_V2_*_BAKED` (un material, texturas horneadas).

    Devuelve {"name", "procedural": [...], "baked": [...]}. Las piezas (base/tapa) salen como objetos separados
    con su origen en la bisagra cuando el generador lo define.
    """
    gen, params = build.resolve_params(spec)
    name = asset_name(spec)
    full = "%s_V2" % name
    combined = build.make_object(dict(spec, name=full + "_malla"), "procedural", collection, location)
    baked = None
    if do_bake:
        baked, _images = bake.bake_object(combined, name, size=size, samples=samples, collection=collection)
        baked.location = combined.location
    parts = getattr(gen, "parts", None)
    result = {"name": full, "procedural": [], "baked": [], "params": params}
    if parts:
        origins = gen.part_origins(params)
        result["procedural"] = build.split_parts(combined, parts, origins, lambda part: "%s_%s" % (full, part), collection)
        if baked is not None:
            result["baked"] = build.split_parts(baked, parts, origins, lambda part: "%s_%s_BAKED" % (full, part),
                                                collection)
        for obj in (combined, baked):
            if obj is not None:
                data = obj.data
                bpy.data.objects.remove(obj)
                if data.users == 0:
                    bpy.data.meshes.remove(data)
        for obj in result["procedural"] + result["baked"]:
            obj.location = (obj.location.x + location[0], obj.location.y + location[1], obj.location.z + location[2]) \
                if False else obj.location
        open_deg = float(params.get("open_deg", 0.0))
        if open_deg:
            for obj in result["procedural"] + result["baked"]:
                if obj.name.endswith("tapa") or obj.name.endswith("tapa_BAKED"):
                    obj.rotation_euler = (radians(-open_deg), 0.0, 0.0)
    else:
        combined.name = "%s_malla" % full
        result["procedural"] = [combined]
        if baked is not None:
            baked.name = "%s_malla_BAKED" % full
            result["baked"] = [baked]
    if not keep_procedural:
        for obj in result["procedural"]:
            data = obj.data
            bpy.data.objects.remove(obj)
            if data.users == 0:
                bpy.data.meshes.remove(data)
        result["procedural"] = []
    else:
        for obj in result["procedural"]:
            obj.hide_viewport = bool(result["baked"])
    return result
