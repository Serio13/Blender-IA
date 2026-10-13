"""Construye un asset a partir de una spec: malla + objeto + materiales."""
import bpy

from . import generators, materials


def make_object(spec, mode="procedural", collection=None, location=(0, 0, 0)):
    """mode: 'procedural' (materiales con nodos) o 'solid' (colores planos)."""
    gen = generators.get(spec["archetype"])()
    params = dict(gen.defaults)
    params.update(gen.variants.get(spec.get("variant"), {}))
    params.update(spec.get("params", {}))
    builder = gen.build(params)
    roles = list(builder.roles)
    mesh = builder.finish()
    mesh["pf_density"] = builder.density
    for role in roles:
        if mode == "solid":
            mesh.materials.append(materials.solid(role))
        else:
            mesh.materials.append(materials.procedural(role, builder.density, params.get("wear", 0.5),
                                                       owner=spec.get("name") or spec["archetype"]))
    obj = bpy.data.objects.new(spec.get("name") or spec["archetype"].capitalize(), mesh)
    (collection or bpy.context.scene.collection).objects.link(obj)
    obj.location = location
    obj["pf_params"] = {k: (v if isinstance(v, (int, float, str, bool)) or v is None else str(v))
                        for k, v in params.items()}
    return obj
