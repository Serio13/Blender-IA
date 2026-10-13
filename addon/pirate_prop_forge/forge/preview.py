"""Vista previa con Cycles en CPU: escena temporal con suelo, luces y camara (no toca tu escena)."""
import bpy
from mathutils import Vector


def render(objects, path, size=(640, 480), samples=24, angle=(2.0, -2.4, 1.55), look=None, ground=True,
           engine="CYCLES"):
    scene = bpy.data.scenes.new("PF_PREVIEW")
    col = bpy.data.collections.new("PF_PREVIEW_COL")
    scene.collection.children.link(col)
    for obj in objects:
        col.objects.link(obj)
    created = []
    try:
        pts = [obj.matrix_basis @ Vector(c) for obj in objects for c in obj.bound_box]   # sin padre: basis = mundo
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        center = (lo + hi) / 2 if look is None else Vector(look)
        diag = (hi - lo).length
        scene.render.engine = engine
        if engine == "CYCLES":
            scene.cycles.device = "CPU"
            scene.cycles.samples = samples
            scene.cycles.use_denoising = False
        scene.render.resolution_x, scene.render.resolution_y = size
        scene.render.film_transparent = False
        world = bpy.data.worlds.new("PF_PREVIEW_W")
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
        bg.inputs["Strength"].default_value = 0.9
        scene.world = world
        created.append(world)
        cam_data = bpy.data.cameras.new("PF_CAM")
        cam_data.lens = 55
        cam = bpy.data.objects.new("PF_CAM", cam_data)
        scene.collection.objects.link(cam)
        direction = Vector(angle).normalized()
        cam.location = center + direction * diag * 2.3
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        sun_data = bpy.data.lights.new("PF_SUN", "SUN")
        sun_data.energy = 3.2
        sun_data.angle = 0.2
        sun = bpy.data.objects.new("PF_SUN", sun_data)
        sun.rotation_euler = (0.85, 0.15, 0.55)
        scene.collection.objects.link(sun)
        fill_data = bpy.data.lights.new("PF_FILL", "AREA")
        fill_data.energy = 60
        fill_data.size = 3
        fill = bpy.data.objects.new("PF_FILL", fill_data)
        fill.location = center + Vector((-2.0, -2.5, 2.0))
        fill.rotation_euler = (1.0, 0, -0.6)
        scene.collection.objects.link(fill)
        if ground:
            gm = bpy.data.meshes.new("PF_GROUND")
            gm.from_pydata([(-6, -6, lo.z), (6, -6, lo.z), (6, 6, lo.z), (-6, 6, lo.z)], [], [(0, 1, 2, 3)])
            g = bpy.data.objects.new("PF_GROUND", gm)
            mat = bpy.data.materials.new("PF_GROUND_M")
            mat.diffuse_color = (0.45, 0.62, 0.3, 1)
            mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.22, 0.4, 0.12, 1)
            gm.materials.append(mat)
            scene.collection.objects.link(g)
            created += [g, gm, mat]
        scene.render.filepath = str(path)
        scene.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True, scene=scene.name)
    finally:
        for obj in list(col.objects):
            col.objects.unlink(obj)
        for ob in list(scene.collection.objects):
            data = ob.data
            bpy.data.objects.remove(ob)
            if data is not None and data.users == 0:
                (bpy.data.cameras if hasattr(data, "lens") and hasattr(data, "sensor_width") else bpy.data.lights).remove(data) \
                    if data.name in (bpy.data.cameras if hasattr(data, "sensor_width") else bpy.data.lights) else None
        bpy.data.scenes.remove(scene)
        bpy.data.collections.remove(col)
        for item in created:
            try:
                if isinstance(item, bpy.types.Object):
                    bpy.data.objects.remove(item)
                elif isinstance(item, bpy.types.Mesh):
                    bpy.data.meshes.remove(item)
                elif isinstance(item, bpy.types.Material):
                    bpy.data.materials.remove(item)
                elif isinstance(item, bpy.types.World):
                    bpy.data.worlds.remove(item)
            except (ReferenceError, RuntimeError):
                pass
    return str(path)
