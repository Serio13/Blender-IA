import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from ..core import postprocess
from ..core.settings import PRESETS


def _preset_items():
    return [(k, k.capitalize(), "LOD1..: " + ", ".join("%d%%" % round(r * 100) for r in v))
            for k, v in PRESETS.items()]


class PF_Settings(bpy.types.PropertyGroup):
    asset_name: StringProperty(name="Nombre", description="Vacio = automatico (solo con un unico asset)")
    preset: EnumProperty(name="Preset LOD", items=_preset_items(), default="estandar")
    min_tris: IntProperty(name="Min. triangulos por LOD", default=24, min=4)
    skip_below: IntProperty(name="Sin LODs bajo", default=300, min=0,
                            description="Assets con menos triangulos no necesitan LODs")
    dissolve_deg: FloatProperty(name="Disolver planos (grados)", default=3.0, min=0.0, max=30.0)
    smooth_deg: FloatProperty(name="Suavizado (grados)", default=35.0, min=0.0, max=180.0)
    spread: BoolProperty(name="Mostrar LODs (separados en X)", default=False,
                         description="Los LODs se ocultan por defecto para no taparse con el original. Marcalo para "
                                     "verlos al lado y revisarlos; la exportacion los recoloca igualmente")
    keep_uv2: BoolProperty(name="Conservar UV adicionales", default=True)
    strict: BoolProperty(name="Descartar LODs que deformen", default=True,
                         description="Si un LOD cambia la forma o la textura, se sube su tamaño o se descarta")

    out_dir: StringProperty(name="Carpeta", subtype="DIR_PATH", default="//Export/")
    export_fbx: BoolProperty(name="FBX", default=True)
    export_blend: BoolProperty(name="Blend", default=True)
    layout: EnumProperty(name="Jerarquia", default="grouped", items=[
        ("grouped", "Agrupada", "Un nodo _LODn por nivel con las piezas dentro"),
        ("flat", "Plana", "Cada pieza como nodo _LODn independiente")])
    collider: EnumProperty(name="Colision", default="hint", items=[
        ("none", "Ninguna", ""),
        ("hint", "Solo datos", "Caja/capsula sugerida en el informe, sin mallas"),
        ("mesh", "Malla _COL", "Casco convexo simplificado con sufijo _COL")])
    pivot: EnumProperty(name="Origen", default="base", items=[
        ("base", "Base", "El centro de la base del asset queda en el origen (recomendado para Unity)"),
        ("center", "Centro", "El centro de la caja del asset queda en el origen"),
        ("keep", "Mantener", "Se respeta el origen actual del objeto")])
    verify: BoolProperty(name="Verificar FBX", default=False)
    last_result: StringProperty(name="Ultimo resultado", default="")
    token_saver: BoolProperty(name="Modo ahorro de tokens", default=True,
                              description="Respuestas minimas y sin informacion extra")

    # ---- IA local
    ai_image: StringProperty(name="Imagen", subtype="FILE_PATH", description="Foto o dibujo del objeto (fondo liso si es posible)")
    ai_name: StringProperty(name="Nombre", default="Prop_ia_V2",
                            description="Familia_variante_V2; la pieza se llama <Nombre>_malla_BAKED")
    ai_backend: EnumProperty(name="Modelo", default="sf3d", items=[
        ("sf3d", "Stable Fast 3D", "Malla con UV y texturas PBR. Licencia Stability Community (gratis comercial < 1 M USD/año)"),
        ("triposr", "TripoSR", "Malla con color por vertice. Licencia MIT"),
        ("fake", "Prueba (sin IA)", "Barril de prueba para comprobar el plugin; no usar en produccion")])
    ai_category: EnumProperty(name="Categoria", default="barril",
                              items=[(k, k.capitalize(), "%s m de alto" % v[0] if v[0] else "Sin escala automatica")
                                     for k, v in postprocess.CATEGORIES.items()])
    ai_height: FloatProperty(name="Alto real (m)", default=0.0, min=0.0, max=50.0, unit="LENGTH",
                             description="0 = el de la categoria. Referencia: el pirata mide 1,62 m")
    ai_pivot: EnumProperty(name="Origen", default="base", items=[
        ("base", "Base", "Centro de la base en el origen"), ("center", "Centro", "Centro de la caja en el origen"),
        ("keep", "Mantener", "Sin mover")])
    ai_budget: EnumProperty(name="Triangulos", default="auto", items=[
        ("auto", "Automatico", "Maximo segun la categoria"), ("manual", "Manual", "Minimo y maximo propios"),
        ("off", "Sin limite", "No reducir")])
    ai_min_tris: IntProperty(name="Minimo", default=300, min=0)
    ai_max_tris: IntProperty(name="Maximo", default=5000, min=50)
    ai_material: EnumProperty(name="Material", default="ia", items=[
        ("ia", "Texturas de la IA", "Conserva color/normal/rugosidad que genera el modelo (o hornea el color por vertice)"),
        ("madera", "Madera", "PBR procedural horneado"), ("cuero", "Cuero", "PBR procedural horneado"),
        ("metal", "Metal", "PBR procedural horneado"), ("none", "Ninguno", "Sin material")])
    ai_tex_size: EnumProperty(name="Textura", default="1024", items=[
        (str(n), "%d px" % n, "") for n in (512, 1024, 2048)])
    ai_use_color: BoolProperty(name="Color propio", default=False)
    ai_color: bpy.props.FloatVectorProperty(name="Color", subtype="COLOR", size=3, min=0.0, max=1.0, default=(0.32, 0.19, 0.09))
    ai_mesh: StringProperty(name="Malla", subtype="FILE_PATH", description=".obj / .glb / .gltf ya generado")


classes = (PF_Settings,)
