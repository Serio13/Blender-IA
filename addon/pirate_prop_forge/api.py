"""API de comandos cortos. Pensada para Claude Code: una linea de entrada, 1-3 lineas de salida.

    import pirate_prop_forge.api as pf
    pf.lods("*_BAKED")                       # genera LOD1/LOD2 sin tocar los originales
    pf.export("Cofre_comun_V2_*_BAKED", out_dir="D:/Unity/Assets/Props")
    pf.profile()                             # perfil de estilo compacto (~1-2 KB)
"""
from pathlib import Path

import bpy

from .core import (ai_client, assets, export as core_export, lods as core_lods, meshutil, postprocess,
                   profile as core_profile, textures)
from .shared import cooldown as _cooldown, licenses as _licenses
from .core.version import VERSION
from .core.errors import PFError
from .core.settings import lod_settings


def _fmt_levels(res):
    return " | ".join("LOD%d %d" % (lv.index, lv.tris) for lv in res.levels)


def _settings_kw(kw):
    keys = ("min_tris", "skip_below", "dissolve_deg", "smooth_deg", "spread", "keep_uv2", "strict")
    return {k: kw.pop(k) for k in keys if k in kw}


def lods(target=None, preset="estandar", ratios=None, tris=None, name=None, verbose=False, **kw):
    """Genera LOD1..N de los assets indicados. Devuelve un resumen corto (una linea por asset)."""
    s = lod_settings(preset, ratios, tris, **_settings_kw(kw))
    if kw:
        raise PFError("argumentos desconocidos: %s" % ", ".join(kw))
    lines = []
    for asset in assets.find_assets(target, name=name):
        res = core_lods.generate_lods(asset, s)
        line = "%s: %s" % (asset.name, _fmt_levels(res))
        if res.notes and (verbose or len(res.levels) == 1):
            line += " (%s)" % "; ".join(res.notes)
        if res.warnings:
            line += " AVISO: " + "; ".join(res.warnings)
        lines.append(line)
    return "\n".join(lines)


def clean(target=None, name=None):
    """Elimina los LODs generados de los assets indicados."""
    removed = [(a.name, core_lods.clear_lods(a)) for a in assets.find_assets(target, name=name)]
    return "LODs eliminados: " + ", ".join("%s=%d" % r for r in removed)


def export(target=None, out_dir=None, preset="estandar", ratios=None, tris=None, name=None,
           formats=("fbx", "blend"), layout="grouped", collider="hint", regenerate=False,
           col_max_tris=48, verify=False, pivot="base", verbose=False, **kw):
    """Genera (o reutiliza) LODs y escribe el paquete: FBX + .blend + Textures + informe JSON."""
    if not out_dir:
        raise PFError("falta out_dir (carpeta de salida)")
    s = lod_settings(preset, ratios, tris, **_settings_kw(kw))
    if kw:
        raise PFError("argumentos desconocidos: %s" % ", ".join(kw))
    opts = core_export.ExportOptions(formats=tuple(formats), layout=layout, collider=collider,
                                     col_max_tris=col_max_tris, keep_uv2=s.keep_uv2, verify=verify, pivot=pivot)
    opts.validate()
    lines = []
    for asset in assets.find_assets(target, name=name):
        res = None if regenerate else core_lods.existing_levels(asset)
        if res is None:
            res = core_lods.generate_lods(asset, s)
        rep = core_export.export_asset(asset, out_dir, res, opts)
        line = "%s: %s -> %s [%s%s]" % (
            asset.name, _fmt_levels(res), rep["package"],
            "+".join(k.upper() for k in rep["files"]), " +%d tex" % len(rep["textures"]) if rep["textures"] else "")
        line += " pivote=%s" % rep["pivot"]
        if rep["warnings"]:
            line += " AVISO: " + "; ".join(rep["warnings"])
        if verbose and rep["notes"]:
            line += " (%s)" % "; ".join(rep["notes"])
        lines.append(line)
    return "\n".join(lines)


def profile(out=None, ref_collection=core_profile.REF_COLLECTION, max_families=core_profile.MAX_FAMILIES):
    """Perfil de estilo compacto. Si out es una ruta, escribe tambien el JSON."""
    prof = core_profile.build_profile(ref_collection, max_families)
    text = core_profile.summarize(prof)
    if out:
        path = core_profile.write_profile(prof, out)
        text += "\n-> %s (%d bytes)" % (path, Path(path).stat().st_size)
    return text


def version():
    """Version instalada del plugin."""
    return VERSION


def check(target=None, name=None):
    """Que va a exportarse de cada asset (piezas, triangulos, texturas reconocidas) sin generar nada."""
    lines = ["Prop Forge v%s" % VERSION]
    for asset in assets.find_assets(target, name=name):
        objs = [p.obj for p in asset.parts]
        tris = sum(meshutil.tri_count(o.data) for o in objs)
        images, unknown = textures.collect_images(objs)
        tex = ", ".join(
            ("%s %d" % (k, max(img.size))) if img.size[0] else ("%s VACIA" % k)
            for k, img in sorted(images.items())) or "SIN TEXTURAS"
        line = "%s: %d pieza(s), %d tris, texturas: %s" % (asset.name, len(asset.parts), tris, tex)
        uv_layers = objs[0].data.uv_layers
        if len(uv_layers):
            render = meshutil.render_uv_index(objs[0].data, textures.render_uv_name(objs))
            marks = ", ".join(layer.name + ("*" if i == render else "") for i, layer in enumerate(uv_layers))
            line_uv = " | UV: " + marks + (" (la de texturas se pondra primera)" if render else "")
        else:
            line_uv = " | SIN UV"
        missing = [k for k in ("BaseMap", "Normal") if k not in images]
        line += line_uv
        if images and missing:
            line += " | FALTA: " + ", ".join(missing)
        if unknown:
            line += " | sin reconocer: " + ", ".join(sorted(set(unknown)))
        lines.append(line)
    return "\n".join(lines)


_AI_KEYS = ("category", "height", "pivot", "budget", "min_tris", "max_tris", "material", "tex_size", "color")


def ai_import(path, name, **kw):
    """Normaliza una malla ya generada (.obj/.glb): limpieza, escala real, origen, triangulos y material PBR.

        pf.ai_import("D:/ia/barril.glb", "Barril_ia_V2", category="barril", material="madera")
    """
    obj, rep = postprocess.process(path, name, postprocess.Options(**{k: kw.pop(k) for k in _AI_KEYS if k in kw}))
    if kw:
        raise PFError("argumentos desconocidos: %s" % ", ".join(kw))
    return postprocess.summary(rep)


def ai_generate(images, names=None, backend="sf3d", python="", cooldown_seconds=10.0, commercial_only=True,
                timeout=900.0, params=None, **kw):
    """Genera con IA local (bloquea hasta terminar; pensado para scripts/Claude Code, no para la interfaz).

    `images`: ruta o lista; con varias se generan una tras otra respetando la pausa de enfriamiento.
    """
    import time
    if commercial_only and not _licenses.commercial_ok(backend):
        raise PFError("'%s' no esta marcado como apto para uso comercial (commercial_only=False para pruebas)" % backend)
    images = [images] if isinstance(images, str) else list(images)
    names = [names] if isinstance(names, str) else list(names or [])
    if len(names) != len(images):
        names = [Path(i).stem for i in images] if not names else names
    if len(names) != len(images):
        raise PFError("hace falta un nombre por imagen")
    opts = postprocess.Options(**{k: kw.pop(k) for k in _AI_KEYS if k in kw}).validate()
    if kw:
        raise PFError("argumentos desconocidos: %s" % ", ".join(kw))
    import tempfile
    out_dir = tempfile.mkdtemp(prefix="pf_ai_")
    cli = ai_client.AIClient(ai_client.find_python(python), backend=backend)
    lines = []
    try:
        cli.start()
        cli.hello({"min_seconds": cooldown_seconds})
        ready, _ = cli.wait_for("ready", timeout=600)
        state = ready["backends"].get(backend, {})
        if not state.get("available"):
            raise PFError("modelo '%s' no disponible: %s" % (backend, state.get("reason", "?")))
        for image, name in zip(images, names):
            while True:
                cli.generate(image, out_dir, name, backend)
                ev, _ = cli.wait_for_any(("result", "error"), timeout=timeout)
                if ev["event"] == "result":
                    break
                if ev.get("code") in ("cooldown", "overheated"):
                    time.sleep(max(1.0, float(ev.get("remaining", 5.0))))
                    continue
                raise PFError("%s: %s" % (name, ev.get("message", ev.get("code"))))
            obj, rep = postprocess.process(ev["mesh"], name, opts)
            meta = _licenses.get(backend) or {}
            obj["pf_source"], obj["pf_license"], obj["pf_commercial_ok"] = backend, meta.get("license", ""), bool(meta.get("commercial_ok"))
            lines.append("%s (%s, %.0f s)" % (postprocess.summary(rep), backend, ev.get("seconds", 0)))
    finally:
        cli.stop()
    return "\n".join(lines)
