import textwrap

import bpy

from ..core import ai_client, ai_session
from ..core.version import VERSION
from ..shared import licenses
from . import prefs as prefs_mod


def draw_result(layout, text, width=42, max_lines=14):
    """Muestra el ultimo resultado dentro del panel (los avisos de la barra de estado desaparecen)."""
    box = layout.box()
    shown = 0
    for line in text.splitlines():
        for chunk in textwrap.wrap(line, width, break_long_words=True) or [""]:
            if shown >= max_lines:
                box.label(text="...")
                return
            box.label(text=chunk)
            shown += 1


class PF_PT_main(bpy.types.Panel):
    bl_label = "Prop Forge"
    bl_idname = "PF_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Prop Forge"

    def draw(self, context):
        pf = context.scene.pf
        self.layout.label(text="Version %s" % VERSION)
        col = self.layout.column(align=True)
        col.prop(pf, "asset_name")
        col.prop(pf, "token_saver")
        row = self.layout.row(align=True)
        row.operator("pf.check", icon="VIEWZOOM")
        row.operator("pf.profile", icon="INFO")
        if pf.last_result:
            draw_result(self.layout, pf.last_result)


class PF_PT_lods(bpy.types.Panel):
    bl_label = "LODs"
    bl_idname = "PF_PT_lods"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Prop Forge"
    bl_parent_id = "PF_PT_main"

    def draw(self, context):
        pf = context.scene.pf
        col = self.layout.column(align=True)
        col.prop(pf, "preset")
        col.prop(pf, "min_tris")
        col.prop(pf, "skip_below")
        col.prop(pf, "dissolve_deg")
        col.prop(pf, "smooth_deg")
        col.prop(pf, "keep_uv2")
        col.prop(pf, "strict")
        col.prop(pf, "spread")
        row = self.layout.row(align=True)
        row.operator("pf.lods", icon="MOD_DECIM")
        row.operator("pf.clean_lods", icon="TRASH", text="")


class PF_PT_export(bpy.types.Panel):
    bl_label = "Exportar a Unity"
    bl_idname = "PF_PT_export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Prop Forge"
    bl_parent_id = "PF_PT_main"

    def draw(self, context):
        pf = context.scene.pf
        col = self.layout.column(align=True)
        col.prop(pf, "out_dir")
        row = col.row(align=True)
        row.prop(pf, "export_fbx", toggle=True)
        row.prop(pf, "export_blend", toggle=True)
        col.prop(pf, "layout")
        col.prop(pf, "pivot")
        col.prop(pf, "collider")
        col.prop(pf, "verify")
        self.layout.operator("pf.export", icon="EXPORT")


class PF_PT_ai(bpy.types.Panel):
    bl_label = "IA local"
    bl_idname = "PF_PT_ai"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Prop Forge"
    bl_parent_id = "PF_PT_main"

    def draw(self, context):
        pf, st, lay = context.scene.pf, ai_session.STATE, self.layout
        running = st.client is not None and st.client.alive()
        prefs = prefs_mod.get(context)
        if not running and not ai_client.find_python(prefs.worker_python if prefs else ""):
            box = lay.box()
            box.label(text="Motor de IA no instalado", icon="ERROR")
            draw_result(box, "1) Abre la carpeta del instalador.\n2) Doble clic en instalar_ia.bat (20-30 min, una vez).\n"
                             "3) Vuelve a Blender y pulsa Iniciar.")
            box.operator("pf.ai_open_installer", icon="FILE_FOLDER")
        row = lay.row(align=True)
        if running:
            row.label(text={"starting": "Arrancando...", "generating": "Generando", "postprocess": "Normalizando",
                            "error": "Error"}.get(st.phase, "Motor listo"), icon="CHECKMARK" if st.phase == "idle" else "TIME")
            row.operator("pf.ai_stop", icon="PAUSE")
        else:
            row.operator("pf.ai_start", icon="PLAY")
            if st.phase == "error":
                draw_result(lay, st.message)
        if st.gpu and st.gpu.get("temp") is not None:
            lay.label(text="GPU %d C" % st.gpu["temp"] if st.temp is None else "GPU %d C" % st.temp, icon="LIGHT_SUN")

        col = lay.column(align=True)
        col.prop(pf, "ai_image")
        col.prop(pf, "ai_name")
        col.prop(pf, "ai_backend")
        meta = licenses.get(pf.ai_backend)
        if meta:
            blocked = prefs is not None and prefs.commercial_only and not meta["commercial_ok"]
            col.label(text="Licencia: %s" % meta["license"], icon="ERROR" if blocked else "CHECKMARK")
        info = st.backends.get(pf.ai_backend)
        if running and info is not None and not info.get("available", True):
            draw_result(lay.box(), "Este modelo no esta instalado: %s. Elige 'Stable Fast 3D'." % info.get("reason", ""))

        box = lay.box()
        box.label(text="Resultado")
        c = box.column(align=True)
        c.prop(pf, "ai_category")
        c.prop(pf, "ai_height")
        c.prop(pf, "ai_pivot")
        c.prop(pf, "ai_budget")
        if pf.ai_budget == "manual":
            r = c.row(align=True)
            r.prop(pf, "ai_min_tris")
            r.prop(pf, "ai_max_tris")
        c.prop(pf, "ai_material")
        if pf.ai_material in ("madera", "cuero", "metal"):
            c.prop(pf, "ai_tex_size")
            r = c.row(align=True)
            r.prop(pf, "ai_use_color")
            if pf.ai_use_color:
                r.prop(pf, "ai_color", text="")
        elif pf.ai_material == "ia":
            c.prop(pf, "ai_tex_size")

        # estado: progreso o pausa de enfriamiento
        why = ai_session.blocked_reason()
        if st.phase == "generating":
            _progress(lay, st.progress, "%s %d%%" % (st.text or "generando", st.progress * 100))
            tail = st.client.stderr_text(3) if st.client else ""
            if tail:
                draw_result(lay, tail, max_lines=5)
            lay.operator("pf.ai_cancel", icon="CANCEL")
        elif st.cooldown_left() > 0 and running:
            total = max(5.0, (prefs.cooldown_seconds if prefs else 10.0))
            _progress(lay, max(0.0, min(1.0, 1.0 - st.cooldown_left() / total)),
                      "Enfriando GPU: %d s%s" % (st.cooldown_left() + 0.99, " (%d C)" % st.temp if st.temp else ""))
        row = lay.row()
        row.enabled = why is None
        row.scale_y = 1.4
        row.operator("pf.ai_generate", icon="MESH_MONKEY")
        if why and running and st.phase == "idle" and st.cooldown_left() <= 0:
            lay.label(text=why)
        if st.message and st.phase != "error":
            draw_result(lay, st.message)

        sub = lay.box()
        sub.label(text="Sin IA: normalizar una malla")
        sub.prop(pf, "ai_mesh")
        sub.operator("pf.ai_import", icon="IMPORT")
        row = lay.row(align=True)
        row.operator("pf.ai_doctor", icon="QUESTION")
        row.operator("pf.ai_open_log", icon="TEXT")
        if st.doctor_text:
            draw_result(lay, st.doctor_text, max_lines=24)


def _progress(layout, factor, text):
    try:
        layout.progress(factor=factor, type="BAR", text=text)
    except (AttributeError, TypeError):
        layout.label(text=text)


classes = (PF_PT_main, PF_PT_lods, PF_PT_export, PF_PT_ai)
