"""Construye un asset a partir de una spec: malla + objeto + materiales; y separa piezas."""
import bmesh
import bpy
from mathutils import Matrix, Vector

from . import generators, materials


def resolve_params(spec):
    gen = generators.get(spec["archetype"])()
    params = dict(gen.defaults)
    params.update(gen.variants.get(spec.get("variant"), {}))
    params.update(spec.get("params", {}))
    return gen, params


def make_object(spec, mode="procedural", collection=None, location=(0, 0, 0)):
    """Un unico objeto con todas las piezas (necesario para hornear un atlas comun).

    mode: 'procedural' (materiales con nodos) o 'solid' (colores planos).
    """
    gen, params = resolve_params(spec)
    builder = gen.build(params)
    roles = list(builder.roles)
    mesh = builder.finish()
    mesh["pf_density"] = builder.density
    owner = spec.get("name") or spec["archetype"]
    for role in roles:
        if mode == "solid":
            mesh.materials.append(materials.solid(role))
        else:
            mesh.materials.append(materials.procedural(role, builder.density, params.get("wear", 0.5), owner=owner))
    obj = bpy.data.objects.new(owner, mesh)
    (collection or bpy.context.scene.collection).objects.link(obj)
    obj.location = location
    obj["pf_params"] = {k: (v if isinstance(v, (int, float, str, bool)) or v is None else str(v))
                        for k, v in params.items()}
    return obj


def split_parts(obj, names, origins, name_for, collection=None):
    """Separa `obj` en un objeto por pieza (atributo pf_part). El origen de cada pieza es origins[nombre]."""
    me = obj.data
    out = []
    layer_name = "pf_part"
    for index, part in enumerate(names):
        bm = bmesh.new()
        bm.from_mesh(me)
        layer = bm.faces.layers.int.get(layer_name)
        doomed = [f for f in bm.faces if f[layer] != index]
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        origin = Vector(origins[part])
        bmesh.ops.translate(bm, vec=-origin, verts=bm.verts)
        new = bpy.data.meshes.new(name_for(part))
        bm.to_mesh(new)
        bm.free()
        for mat in me.materials:
            new.materials.append(mat)
        child = bpy.data.objects.new(name_for(part), new)
        (collection or bpy.context.scene.collection).objects.link(child)
        child.matrix_world = obj.matrix_world @ Matrix.Translation(origin)
        out.append(child)
    return out
