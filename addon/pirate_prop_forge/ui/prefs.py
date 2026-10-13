import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty

from ..core import ai_client

PACKAGE = __package__.rsplit(".", 1)[0]


class PF_Preferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE

    worker_python: StringProperty(name="Python del entorno de IA", subtype="FILE_PATH", default="",
                                  description="Vacio = el que dejo instalar_ia.bat")
    hf_token: StringProperty(name="Token de Hugging Face", subtype="PASSWORD", default="",
                             description="Solo si no hiciste 'huggingface-cli login' en la instalacion")
    commercial_only: BoolProperty(name="Solo modelos aptos para uso comercial", default=True,
                                  description="Bloquea modelos marcados como solo de prueba. Desmarca solo para experimentar, "
                                              "y no vendas lo generado con ellos")
    cooldown_seconds: FloatProperty(name="Pausa entre generaciones (s)", default=10.0, min=5.0, max=15.0,
                                    description="Pausa obligatoria que protege la GPU (5-15 s)")
    cooldown_adaptive: BoolProperty(name="Esperar tambien a que la GPU se enfrie", default=True)
    resume_temp: FloatProperty(name="Reanudar por debajo de (C)", default=72.0, min=50.0, max=90.0)
    abort_temp: FloatProperty(name="No aceptar trabajo desde (C)", default=85.0, min=60.0, max=95.0)
    unload_after: BoolProperty(name="Descargar el modelo tras cada generacion", default=False,
                               description="Libera ~6 GB de VRAM entre trabajos; la siguiente generacion tarda mas en empezar")

    def policy(self):
        return {"min_seconds": self.cooldown_seconds, "adaptive": self.cooldown_adaptive,
                "resume_temp": self.resume_temp, "abort_temp": self.abort_temp}

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Motor de IA local", icon="PREFERENCES")
        col.prop(self, "worker_python")
        py = ai_client.find_python(self.worker_python)
        col.label(text=("Usando: " + py) if py else "No hay entorno de IA: ejecuta instalar_ia.bat", icon="CHECKMARK" if py else "ERROR")
        col.prop(self, "hf_token")
        col.separator()
        col.label(text="Proteccion de la GPU")
        col.prop(self, "cooldown_seconds")
        col.prop(self, "cooldown_adaptive")
        sub = col.column(align=True)
        sub.prop(self, "resume_temp")
        sub.prop(self, "abort_temp")
        col.prop(self, "unload_after")
        col.separator()
        col.prop(self, "commercial_only")


def get(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(PACKAGE)
    return addon.preferences if addon else None


classes = (PF_Preferences,)
