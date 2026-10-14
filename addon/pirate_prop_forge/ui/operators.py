import bpy

from .. import api
from ..core import ai_session, postprocess
from ..core.errors import PFError
from ..shared import licenses
from . import prefs as prefs_mod
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


# --------------------------------------------------------------------------------------------------------------
# IA local
# --------------------------------------------------------------------------------------------------------------
def _ai_options(pf):
    return postprocess.Options(
        category=pf.ai_category, height=pf.ai_height, pivot=pf.ai_pivot, budget=pf.ai_budget, min_tris=pf.ai_min_tris,
        max_tris=pf.ai_max_tris, material=pf.ai_material, tex_size=int(pf.ai_tex_size), smooth=pf.ai_smooth,
        color=tuple(pf.ai_color) if pf.ai_use_color else None).validate()


def _check_license(backend, prefs):
    meta = licenses.get(backend)
    if meta is None:
        raise PFError("modelo desconocido: %s" % backend)
    if prefs is not None and prefs.commercial_only and not meta["commercial_ok"]:
        raise PFError("'%s' esta marcado como solo de prueba. Para usarlo desmarca 'Solo modelos aptos para uso "
                      "comercial' en Preferencias (y no vendas lo generado)" % backend)


class _AIOperator(bpy.types.Operator):
    bl_options = {"REGISTER"}

    def run(self, context, pf, prefs):
        raise NotImplementedError

    def execute(self, context):
        pf = context.scene.pf
        try:
            self.run(context, pf, prefs_mod.get(context))
        except PFError as exc:
            ai_session.STATE.message = "ERROR: %s" % exc
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class PF_OT_ai_start(_AIOperator):
    bl_idname = "pf.ai_start"
    bl_label = "Iniciar motor de IA"
    bl_description = "Arranca el proceso de IA local (no bloquea Blender)"

    def run(self, context, pf, prefs):
        ai_session.start(python=prefs.worker_python if prefs else "", token=prefs.hf_token if prefs else "",
                         policy=prefs.policy() if prefs else None)


class PF_OT_ai_stop(_AIOperator):
    bl_idname = "pf.ai_stop"
    bl_label = "Apagar"
    bl_description = "Cierra el motor de IA y libera la memoria de la GPU"

    def run(self, context, pf, prefs):
        ai_session.stop()


class PF_OT_ai_generate(_AIOperator):
    bl_idname = "pf.ai_generate"
    bl_label = "Generar malla"
    bl_description = "Genera la malla con IA local y la normaliza (escala real, origen, triangulos, material)"

    def run(self, context, pf, prefs):
        _check_license(pf.ai_backend, prefs)
        params = None
        if pf.ai_source == "TEXT":
            if not pf.ai_prompt.strip():
                raise PFError("escribe que quieres en 'Describe' (mejor en ingles)")
            _check_license("sd15", prefs)
            params = {"prompt": pf.ai_prompt.strip(), "seed": pf.ai_seed,
                      "image_model": "fake" if pf.ai_backend == "fake" else "sd15"}
            image = ""
        else:
            image = bpy.path.abspath(pf.ai_image)
        ai_session.generate(image, pf.ai_name, pf.ai_backend, _ai_options(pf), params=params,
                            unload_after=bool(prefs and prefs.unload_after))


class PF_OT_ai_cancel(_AIOperator):
    bl_idname = "pf.ai_cancel"
    bl_label = "Cancelar"

    def run(self, context, pf, prefs):
        ai_session.cancel()


class PF_OT_ai_import(_AIOperator):
    bl_idname = "pf.ai_import"
    bl_label = "Normalizar malla existente"
    bl_description = "Importa un .obj/.glb ya generado y le aplica limpieza, escala, origen, triangulos y material"
    bl_options = {"REGISTER", "UNDO"}

    def run(self, context, pf, prefs):
        ai_session.import_existing(bpy.path.abspath(pf.ai_mesh), pf.ai_name, _ai_options(pf))


class PF_OT_ai_doctor(_AIOperator):
    bl_idname = "pf.ai_doctor"
    bl_label = "Diagnosticar"
    bl_description = "Comprueba GPU, PyTorch, modelos y permisos (tarda unos segundos)"

    def run(self, context, pf, prefs):
        ai_session.run_doctor(prefs.worker_python if prefs else "")


class PF_OT_ai_open_installer(_AIOperator):
    bl_idname = "pf.ai_open_installer"
    bl_label = "Abrir carpeta del instalador"
    bl_description = "Abre la carpeta que contiene instalar_ia.bat; haz doble clic en ese archivo"

    def run(self, context, pf, prefs):
        from pathlib import Path
        folder = Path(__file__).resolve().parent.parent / "worker"
        bpy.ops.wm.path_open(filepath=str(folder))


class PF_OT_ai_use_image(_AIOperator):
    bl_idname = "pf.ai_use_image"
    bl_label = "Usar esta imagen"
    bl_description = "Pasa la imagen creada a 'Imagen' para rehacer la malla sin volver a dibujarla"

    def run(self, context, pf, prefs):
        if not pf.ai_last_image:
            raise PFError("todavia no se ha creado ninguna imagen")
        pf.ai_image = pf.ai_last_image
        pf.ai_source = "IMAGE"


class PF_OT_ai_open_log(_AIOperator):
    bl_idname = "pf.ai_open_log"
    bl_label = "Ver registro"
    bl_description = "Abre el registro del motor de IA (worker.log); util para diagnosticar si algo se atasca"

    def run(self, context, pf, prefs):
        from ..core import ai_client
        path = ai_client.log_file()
        if not path.exists():
            raise PFError("todavia no hay registro: inicia el motor de IA primero")
        bpy.ops.wm.path_open(filepath=str(path))


classes = (PF_OT_lods, PF_OT_clean, PF_OT_export, PF_OT_check, PF_OT_profile, PF_OT_ai_open_installer, PF_OT_ai_open_log, PF_OT_ai_use_image,
           PF_OT_ai_start, PF_OT_ai_stop, PF_OT_ai_generate, PF_OT_ai_cancel, PF_OT_ai_import, PF_OT_ai_doctor)
