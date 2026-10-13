import bpy

from .. import api
from ..core.errors import PFError
from ..core.settings import PRESETS


def _common(pf):
    return dict(
        preset=pf.preset, name=pf.asset_name or None, min_tris=pf.min_tris, skip_below=pf.skip_below,
        dissolve_deg=pf.dissolve_deg, smooth_deg=pf.smooth_deg, spread=pf.spread, keep_uv2=pf.keep_uv2, strict=pf.strict,
    )


class _PFOperator(bpy.types.Operator):
    bl_options = {"REGISTER", "UNDO"}

    def run(self, context, pf):
        raise NotImplementedError

    def execute(self, context):
        pf = context.scene.pf
        try:
            text = self.run(context, pf)
        except PFError as exc:
            pf.last_result = "ERROR: %s" % exc
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        pf.last_result = text
        for line in text.splitlines():
            self.report({"INFO"}, line)
        if not pf.token_saver:
            print(text)
        return {"FINISHED"}


class PF_OT_lods(_PFOperator):
    bl_idname = "pf.lods"
    bl_label = "Generar LODs"
    bl_description = "Genera LOD1..N de los objetos seleccionados (los originales no se tocan)"

    def run(self, context, pf):
        return api.lods(None, verbose=not pf.token_saver, **_common(pf))


class PF_OT_clean(_PFOperator):
    bl_idname = "pf.clean_lods"
    bl_label = "Quitar LODs"
    bl_description = "Elimina los LODs generados de los objetos seleccionados"

    def run(self, context, pf):
        return api.clean(None, name=pf.asset_name or None)


class PF_OT_export(_PFOperator):
    bl_idname = "pf.export"
    bl_label = "Exportar paquete"
    bl_description = "FBX + .blend + texturas PNG + informe, con los LODs existentes (o nuevos)"

    def run(self, context, pf):
        formats = tuple(f for f, on in (("fbx", pf.export_fbx), ("blend", pf.export_blend)) if on)
        return api.export(None, out_dir=bpy.path.abspath(pf.out_dir), formats=formats, layout=pf.layout,
                          collider=pf.collider, pivot=pf.pivot, verify=pf.verify, verbose=not pf.token_saver, **_common(pf))


class PF_OT_check(_PFOperator):
    bl_idname = "pf.check"
    bl_label = "Revisar seleccion"
    bl_description = "Muestra que texturas reconoce el plugin en los objetos seleccionados (no genera nada)"
    bl_options = {"REGISTER"}

    def run(self, context, pf):
        return api.check(None, name=pf.asset_name or None)


class PF_OT_profile(_PFOperator):
    bl_idname = "pf.profile"
    bl_label = "Perfil de estilo"
    bl_description = "Resumen compacto de la escena (se escribe junto al .blend si esta guardado)"

    def run(self, context, pf):
        out = None
        if bpy.data.filepath:
            out = bpy.path.abspath("//style_profile.json")
        return api.profile(out)


classes = (PF_OT_lods, PF_OT_clean, PF_OT_export, PF_OT_check, PF_OT_profile)
