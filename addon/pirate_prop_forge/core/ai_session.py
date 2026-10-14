"""Sesion de IA dentro de Blender: arranca el worker, recibe sus eventos con un temporizador (sin bloquear la
interfaz) y, al llegar la malla, la normaliza en el hilo principal.
"""
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import bpy

from . import ai_client, postprocess
from .errors import PFError
from ..shared import licenses

POLL_SECONDS = 0.25


@dataclass
class State:
    client: object = None
    phase: str = "off"            # off | starting | idle | generating | postprocess | error
    progress: float = 0.0
    text: str = ""
    job: dict = field(default_factory=dict)
    cooldown_until: float = 0.0   # time.monotonic() en el que acaba la pausa
    cooldown_reason: str = ""
    temp: float = None
    backends: dict = field(default_factory=dict)
    image_models: dict = field(default_factory=dict)
    last_image: str = ""
    last_prompt: str = ""
    gpu: dict = None
    message: str = ""             # ultimo resultado/aviso para el panel
    doctor_text: str = ""
    last_object: str = ""

    def cooldown_left(self):
        return max(0.0, self.cooldown_until - time.monotonic())


STATE = State()
_registered = False


def reset_state():
    """Para pruebas."""
    stop()
    STATE.__dict__.update(State().__dict__)


# --------------------------------------------------------------------------------------------------------------
def start(python="", backend=None, token="", policy=None):
    if STATE.client is not None and STATE.client.alive():
        return
    py = ai_client.find_python(python)
    env = {"HF_TOKEN": token} if token else {}
    STATE.client = ai_client.AIClient(py, backend=backend, env=env)
    STATE.client.start()
    STATE.client.hello(policy)
    STATE.phase, STATE.message, STATE.progress, STATE.text = "starting", "Arrancando el motor de IA...", 0.0, ""
    _ensure_timer()


def stop():
    if STATE.client is not None:
        STATE.client.stop()
    STATE.client = None
    STATE.phase, STATE.progress, STATE.text = "off", 0.0, ""
    STATE.cooldown_until = 0.0


def busy():
    return STATE.phase in ("generating", "postprocess")


def blocked_reason():
    """Texto si NO se puede lanzar una generacion ahora (None si se puede)."""
    if STATE.client is None or not STATE.client.alive():
        return "El motor de IA no esta en marcha"
    if STATE.phase == "starting":
        return "El motor de IA esta arrancando"
    if busy():
        return "Hay una generacion en curso"
    left = STATE.cooldown_left()
    if left > 0:
        return "Enfriando la GPU: %d s%s" % (int(left + 0.99), " (%d C)" % STATE.temp if STATE.temp else "")
    return None


def generate(image, name, backend, opts, params=None, unload_after=False, out_dir=None):
    reason = blocked_reason()
    if reason:
        raise PFError(reason)
    prompt = ((params or {}).get("prompt") or "").strip()
    if not prompt and not Path(image).is_file():
        raise PFError("no existe la imagen: %s" % image)
    if prompt:
        im = STATE.image_models.get((params or {}).get("image_model", "sd15"))
        if im is not None and not im.get("available", True):
            raise PFError("texto a imagen no esta instalado (%s). Vuelve a ejecutar instalar_ia.bat" % im.get("reason", ""))
    info = STATE.backends.get(backend)
    if info is not None and not info.get("available", True):
        raise PFError("el modelo '%s' no esta instalado (%s). Elige otro en 'Modelo'" % (backend, info.get("reason", "")))
    out_dir = out_dir or tempfile.mkdtemp(prefix="pf_ai_")
    jid = STATE.client.generate(image, out_dir, name, backend, params, unload_after)
    STATE.job = {"id": jid, "name": name, "opts": opts, "backend": backend, "t0": time.monotonic()}
    STATE.phase, STATE.progress, STATE.text, STATE.message = "generating", 0.0, "enviando", ""
    _ensure_timer()


def cancel():
    if STATE.client is not None and STATE.phase == "generating":
        STATE.client.cancel()
        STATE.text = "cancelando..."


def import_existing(path, name, opts):
    """Normaliza una malla ya existente (sin IA). Sincrono."""
    obj, rep = postprocess.process(path, name, opts)
    STATE.last_object = obj.name
    STATE.message = postprocess.summary(rep)
    return obj, rep


# --------------------------------------------------------------------------------------------------------------
def handle_event(ev):
    """Aplica un evento del worker al estado. Separado del temporizador para poder probarlo."""
    kind = ev.get("event")
    if kind == "ready":
        STATE.backends, STATE.gpu = ev.get("backends", {}), ev.get("gpu")
        STATE.image_models = ev.get("image_models", {})
        cd = ev.get("cooldown") or {}
        if STATE.phase == "starting":
            STATE.phase, STATE.message = "idle", "Motor de IA listo"
        _set_cooldown(cd)
    elif kind == "progress" and STATE.phase == "generating":
        STATE.progress, STATE.text = float(ev.get("fraction", 0.0)), ev.get("text", "")
    elif kind == "image":
        STATE.last_image, STATE.last_prompt = ev.get("path", ""), ev.get("prompt", "")
        try:                                   # deja la imagen creada como referencia visible en el panel
            bpy.context.scene.pf.ai_last_image = STATE.last_image
        except Exception:                      # noqa: BLE001
            pass
    elif kind == "cooldown":
        _set_cooldown(ev)
    elif kind == "cooldown_done":
        STATE.cooldown_until, STATE.cooldown_reason = 0.0, ""
        STATE.temp = ev.get("temp", STATE.temp)
    elif kind == "result":
        _on_result(ev)
    elif kind == "error":
        _on_error(ev)
    elif kind == "exit":
        if STATE.phase not in ("off",):
            tail = STATE.client.stderr_text(4) if STATE.client else ""
            STATE.phase = "error"
            STATE.message = "El motor de IA se ha cerrado" + (": " + tail if tail else "")
            STATE.job = {}


def _set_cooldown(cd):
    STATE.temp = cd.get("temp", STATE.temp)
    if cd.get("ready", True):
        STATE.cooldown_until, STATE.cooldown_reason = 0.0, ""
    else:
        STATE.cooldown_until = time.monotonic() + float(cd.get("remaining", 0.0))
        STATE.cooldown_reason = cd.get("reason") or ""


def _on_result(ev):
    job = STATE.job
    if ev.get("id") != job.get("id"):
        return
    STATE.phase, STATE.progress, STATE.text = "postprocess", 1.0, "normalizando la malla"
    try:
        obj, rep = postprocess.process(ev["mesh"], job["name"], job["opts"])
        meta = licenses.get(ev.get("backend")) or {}
        obj["pf_source"] = ev.get("backend", "")                 # procedencia: util para vender o auditar
        obj["pf_license"] = meta.get("license", "")
        obj["pf_commercial_ok"] = bool(meta.get("commercial_ok"))
        STATE.last_object = obj.name
        STATE.message = "%s (%s, %.0f s)" % (postprocess.summary(rep), ev.get("backend"), ev.get("seconds", 0))
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        STATE.phase = "idle"
    except Exception as exc:                                  # noqa: BLE001
        STATE.phase, STATE.message = "idle", "ERROR al normalizar: %s" % exc
    STATE.job = {}
    _local_cooldown()


def _on_error(ev):
    code = ev.get("code")
    if code in ("cooldown", "overheated"):
        _set_cooldown({"ready": False, "remaining": ev.get("remaining", 5.0), "temp": ev.get("temp"), "reason": code})
        STATE.message = ev.get("message", "")
    else:
        STATE.message = {"oom": "ERROR: sin memoria de GPU (cierra otros programas o usa una imagen mas simple). ",
                         "cancelled": "Generacion cancelada. "}.get(code, "ERROR: ") + (
            "" if code in ("oom", "cancelled") else ev.get("message", ""))
        if code == "oom":
            STATE.message += ev.get("message", "")
        _local_cooldown()
    if STATE.phase in ("generating", "postprocess"):
        STATE.phase = "idle"
    STATE.job = {}


def _local_cooldown(seconds=5.0):
    """Hasta que el worker confirme la pausa real, el boton ya queda bloqueado."""
    STATE.cooldown_until = max(STATE.cooldown_until, time.monotonic() + seconds)


def pump():
    """Procesa los eventos pendientes. Devuelve True si hay que seguir llamandola."""
    cli = STATE.client
    if cli is None:
        return False
    for ev in cli.poll():
        handle_event(ev)
    return STATE.phase != "off" and (cli.alive() or not cli.events.empty())


def _tick():
    try:
        keep = pump()
    except Exception as exc:                                  # noqa: BLE001
        STATE.message = "ERROR interno: %s" % exc
        keep = True
    _redraw()
    return POLL_SECONDS if keep else None


def _ensure_timer():
    global _registered
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=POLL_SECONDS, persistent=True)
    _registered = True


def _redraw():
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", []):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# --------------------------------------------------------------------------------------------------------------
def run_doctor(python="", on_done=None):
    """Lanza worker/doctor.py en un hilo y deja el informe en STATE.doctor_text."""
    import subprocess
    import threading
    py = ai_client.find_python(python)
    if not py or not Path(py).is_file():
        STATE.doctor_text = "No hay Python de IA. Ejecuta instalar_ia.bat (o indica la ruta en Preferencias)."
        return

    def work():
        try:
            out = subprocess.run([py, str(ai_client.DOCTOR_SCRIPT)], capture_output=True, text=True, timeout=180,
                                 encoding="utf-8", errors="replace")
            STATE.doctor_text = (out.stdout or out.stderr or "sin salida").strip()
        except Exception as exc:                              # noqa: BLE001
            STATE.doctor_text = "El diagnostico fallo: %s" % exc
    STATE.doctor_text = "Diagnosticando..."
    threading.Thread(target=work, daemon=True).start()
