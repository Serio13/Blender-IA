import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

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
    spread: BoolProperty(name="Separar LODs en X", default=False,
                         description="Solo para revisarlos en Blender; la exportacion los recoloca")
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


classes = (PF_Settings,)
