"""Linea de comandos para Blender sin interfaz (Windows incluido).

    blender.exe -b archivo.blend --python <ruta>/pirate_prop_forge/cli.py -- export \
        --target "*_BAKED" --out D:/Unity/Assets/Props
    blender.exe -b archivo.blend --python <ruta>/pirate_prop_forge/cli.py -- lods --target Cofre_comun_V2_*_BAKED --save
    blender.exe -b archivo.blend --python <ruta>/pirate_prop_forge/cli.py -- profile --out style_profile.json

Todo lo que va despues de `--` lo interpreta este script.
"""
import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # ejecutado con --python: hace importable el paquete
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pirate_prop_forge import api
    from pirate_prop_forge.core.errors import PFError
    from pirate_prop_forge.core.settings import PRESETS
else:
    from . import api
    from .core.errors import PFError
    from .core.settings import PRESETS


def _floats(text):
    return tuple(float(x) for x in text.split(",") if x.strip())


def _ints(text):
    return tuple(int(x) for x in text.split(",") if x.strip())


def build_parser():
    p = argparse.ArgumentParser(prog="pirate_prop_forge", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--target", help="objeto, coleccion o patron (*, ?). Sin esto: seleccion")
        sp.add_argument("--name", help="nombre del asset (solo si hay un unico asset)")
        sp.add_argument("--preset", default="estandar", choices=sorted(PRESETS))
        sp.add_argument("--ratios", type=_floats, help="ratios de LOD1.. p. ej. 0.35,0.1")
        sp.add_argument("--tris", type=_ints, help="triangulos absolutos de LOD1.. p. ej. 4300,1200")
        sp.add_argument("--min-tris", type=int, dest="min_tris")
        sp.add_argument("--skip-below", type=int, dest="skip_below")
        sp.add_argument("--dissolve-deg", type=float, dest="dissolve_deg")
        sp.add_argument("--smooth-deg", type=float, dest="smooth_deg")
        sp.add_argument("--spread", action="store_true", default=None)
        sp.add_argument("--drop-uv2", action="store_true", help="descarta capas UV adicionales")
        sp.add_argument("-v", "--verbose", action="store_true")

    sp = sub.add_parser("lods", help="genera LOD1..N en la escena")
    common(sp)
    sp.add_argument("--save", action="store_true", help="guarda el .blend abierto despues")

    sp = sub.add_parser("export", help="paquete FBX + .blend + texturas + informe")
    common(sp)
    sp.add_argument("--out", required=True, help="carpeta de salida")
    sp.add_argument("--layout", default="grouped", choices=("grouped", "flat"))
    sp.add_argument("--collider", default="hint", choices=("none", "hint", "mesh"))
    sp.add_argument("--pivot", default="base", choices=("base", "center", "keep"),
                    help="origen del asset: base (por defecto), center o keep (el actual)")
    sp.add_argument("--no-fbx", action="store_true")
    sp.add_argument("--no-blend", action="store_true")
    sp.add_argument("--regenerate", action="store_true", help="vuelve a generar los LODs")
    sp.add_argument("--verify", action="store_true", help="reimporta el FBX para comprobarlo")

    sp = sub.add_parser("clean", help="elimina los LODs generados")
    sp.add_argument("--target")
    sp.add_argument("--name")
    sp.add_argument("--save", action="store_true")

    sp = sub.add_parser("profile", help="perfil de estilo compacto")
    sp.add_argument("--out", help="escribe el JSON aqui")
    return p


def _kw(args):
    kw = {k: getattr(args, k) for k in ("min_tris", "skip_below", "dissolve_deg", "smooth_deg", "spread")
          if getattr(args, k, None) is not None}
    if getattr(args, "drop_uv2", False):
        kw["keep_uv2"] = False
    return kw


def run(argv):
    args = build_parser().parse_args(argv)
    common_kw = dict(preset=getattr(args, "preset", "estandar"), ratios=getattr(args, "ratios", None),
                     tris=getattr(args, "tris", None), name=getattr(args, "name", None),
                     verbose=getattr(args, "verbose", False))
    if args.cmd == "lods":
        out = api.lods(args.target, **common_kw, **_kw(args))
    elif args.cmd == "export":
        formats = tuple(f for f, off in (("fbx", args.no_fbx), ("blend", args.no_blend)) if not off)
        out = api.export(args.target, out_dir=args.out, formats=formats, layout=args.layout,
                         collider=args.collider, regenerate=args.regenerate, verify=args.verify,
                         pivot=args.pivot,
                         **common_kw, **_kw(args))
    elif args.cmd == "clean":
        out = api.clean(args.target, name=args.name)
    else:
        out = api.profile(args.out)
    if getattr(args, "save", False):
        import bpy
        bpy.ops.wm.save_mainfile()
        out += "\nguardado: " + bpy.data.filepath
    return out


def main(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    try:
        print(run(argv))
        return 0
    except PFError as exc:
        print("ERROR: %s" % exc)
        return 1


if __name__ == "__main__" or __package__ in (None, ""):
    code = main()
    if code:
        sys.exit(code)
