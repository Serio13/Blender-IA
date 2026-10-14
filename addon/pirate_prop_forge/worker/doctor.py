"""Diagnostico del entorno de IA: GPU, PyTorch/CUDA, modulos y acceso al modelo. Salida corta y en castellano.

    python doctor.py            (usa el Python del entorno de IA)
Cada linea empieza por OK / FALLA / AVISO. La ultima linea es el veredicto.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

lines, bad, warn = [], [], []


def ok(msg):
    lines.append("OK     " + msg)


def fail(msg, hint=""):
    lines.append("FALLA  " + msg + ((" -> " + hint) if hint else ""))
    bad.append(msg)


def aviso(msg):
    lines.append("AVISO  " + msg)
    warn.append(msg)


def has(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def check_python():
    v = sys.version_info
    (ok if (3, 9) <= v[:2] <= (3, 12) else aviso)("Python %d.%d.%d" % v[:3] + ("" if v[:2] <= (3, 12) else " (SF3D se probo con 3.9-3.12)"))


def check_smi():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,temperature.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=6)
    except (OSError, subprocess.SubprocessError):
        return fail("nvidia-smi no responde", "instala/actualiza el driver de NVIDIA")
    if out.returncode or not out.stdout.strip():
        return fail("nvidia-smi fallo", "instala/actualiza el driver de NVIDIA")
    name, drv, total, used, temp = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")[:5]]
    ok("GPU %s, driver %s, VRAM %s/%s MiB, %s C" % (name, drv, used, total, temp))
    try:
        if float(total) < 7000:
            aviso("VRAM menor de 8 GB: SF3D y TripoSR pueden quedarse sin memoria")
        if float(used) > 2500:
            aviso("hay %s MiB de VRAM ocupados por otros programas (cierra Unity/Chrome antes de generar)" % used)
    except ValueError:
        pass


def check_torch():
    if not has("torch"):
        return fail("PyTorch no esta instalado", "ejecuta instalar_ia.bat")
    import torch
    ok("PyTorch %s (CUDA %s)" % (torch.__version__, torch.version.cuda))
    if not torch.cuda.is_available():
        return fail("PyTorch no ve la GPU", "version CPU instalada o driver antiguo; reinstala con instalar_ia.bat")
    cap = torch.cuda.get_device_capability(0)
    arch = "sm_%d%d" % cap
    archs = torch.cuda.get_arch_list()
    msg = "arquitectura %s %s en esta version de PyTorch (%s)" % (arch, "incluida" if arch in archs else "NO incluida", " ".join(archs))
    if arch in archs:
        ok(msg)
    else:
        fail(msg, "usa PyTorch 2.6 con CUDA 12.4 o 12.6 (las versiones nuevas quitan GPUs Pascal)")
    ok("bf16 %s -> %s" % ("si" if cap[0] >= 8 else "no", "rapido" if cap[0] >= 8 else "se usara FP32 (correcto en GTX 1080 Ti)"))
    try:
        import time
        a = torch.randn(2048, 2048, device="cuda")
        torch.cuda.synchronize()
        t = time.time()
        for _ in range(10):
            a = a @ a / 45.0
        torch.cuda.synchronize()
        ok("prueba de calculo en GPU (%.2f s)" % (time.time() - t))
    except Exception as exc:                               # noqa: BLE001
        fail("la GPU no ejecuta calculos: %s" % exc)


def check_modules():
    needed = [("sf3d", "SF3D"), ("texture_baker", "SF3D texture_baker"), ("uv_unwrapper", "SF3D uv_unwrapper"),
              ("rembg", "rembg"), ("onnxruntime", "onnxruntime"), ("trimesh", "trimesh"), ("PIL", "Pillow"),
              ("huggingface_hub", "huggingface_hub")]
    missing = [label for mod, label in needed if not has(mod)]
    if missing:
        fail("faltan modulos: " + ", ".join(missing), "ejecuta instalar_ia.bat; texture_baker/uv_unwrapper necesitan "
             "las Build Tools de Visual Studio (C++)")
    else:
        ok("modulos de SF3D completos")
    (ok if has("tsr") else aviso)("TripoSR (tsr) " + ("instalado" if has("tsr") else "no instalado (opcional)"))


def check_sf3d_import():
    """Importa SF3D de verdad (carga torch, texture_baker, uv_unwrapper...): detecta DLL rotas y mide el tiempo."""
    if not (has("torch") and has("sf3d")):
        return
    import time
    t = time.time()
    try:
        from sf3d.system import SF3D  # noqa: F401
        import texture_baker, uv_unwrapper  # noqa: F401
    except Exception as exc:                               # noqa: BLE001
        return fail("no se puede importar SF3D: %s: %s" % (type(exc).__name__, exc),
                    "copia este mensaje completo")
    ok("SF3D se importa bien (%.0f s; la primera vez tarda mas por el antivirus)" % (time.time() - t))


def hf_token():
    tok = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if tok:
        return tok
    for p in (Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "token",):
        if p.is_file():
            return p.read_text().strip()
    return ""


def check_model():
    if not has("huggingface_hub"):
        return
    tok = hf_token()
    if not tok:
        return fail("sin token de Hugging Face", "SF3D es un modelo con acceso restringido: acepta la licencia en "
                    "huggingface.co/stabilityai/stable-fast-3d y ejecuta 'huggingface-cli login'")
    try:
        from huggingface_hub import hf_hub_download
        hf_hub_download("stabilityai/stable-fast-3d", "config.yaml", token=tok)
        ok("acceso al modelo SF3D concedido")
    except Exception as exc:                               # noqa: BLE001
        name = type(exc).__name__
        if "Gated" in name or "401" in str(exc) or "403" in str(exc):
            fail("sin permiso para SF3D", "abre huggingface.co/stabilityai/stable-fast-3d con tu cuenta y pulsa 'Agree'")
        else:
            aviso("no se pudo comprobar el acceso al modelo (%s); revisa la conexion" % name)


def check_disk():
    cache = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    probe = cache if cache.exists() else Path.home()
    free = shutil.disk_usage(probe).free / 2 ** 30
    (ok if free > 6 else aviso)("espacio libre para modelos: %.0f GB" % free)


def main():
    for check in (check_python, check_smi, check_torch, check_modules, check_sf3d_import, check_model, check_disk):
        try:
            check()
        except Exception as exc:                           # noqa: BLE001
            fail("%s: %s" % (check.__name__, exc))
    lines.append("VEREDICTO: " + ("LISTO para generar" + (" (con %d avisos)" % len(warn) if warn else "")
                                  if not bad else "%d problema(s) por resolver" % len(bad)))
    print("\n".join(lines))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
