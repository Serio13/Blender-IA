"""Cliente del worker de IA: lanza el proceso, lee sus eventos en hilos y nunca bloquea a Blender.

Sin bpy: se prueba con Python normal. `poll()` devuelve los eventos pendientes sin esperar.
"""
import collections
import itertools
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from ..shared import protocol
from .errors import PFError

WORKER_SCRIPT = Path(__file__).resolve().parent.parent / "worker" / "worker_main.py"
DOCTOR_SCRIPT = Path(__file__).resolve().parent.parent / "worker" / "doctor.py"


def env_file():
    """Archivo que escribe el instalador de Windows con la ruta del Python de IA."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "PiratePropForge" / "worker_env.json"


def find_python(configured=""):
    """Python del entorno de IA: el configurado en preferencias o el que dejo el instalador."""
    if configured:
        return configured
    import json
    try:
        data = json.loads(env_file().read_text(encoding="utf-8"))
        return data.get("python", "")
    except (OSError, ValueError):
        return ""


class AIClient:
    def __init__(self, python, backend=None, env=None, script=None):
        if not python or not Path(python).is_file():
            raise PFError("no se encuentra el Python del entorno de IA (%s). Ejecuta instalar_ia.bat o indica la ruta "
                          "en Preferencias del plugin" % (python or "sin configurar"))
        self.python, self.backend, self.script = str(python), backend, str(script or WORKER_SCRIPT)
        self.env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", **(env or {}))
        self.proc = None
        self.events = queue.Queue()
        self.stderr_tail = collections.deque(maxlen=60)
        self._ids = itertools.count(1)
        self._threads = []

    # -- ciclo de vida
    def start(self):
        if self.alive():
            return
        cmd = [self.python, "-u", self.script]
        if self.backend:
            cmd += ["--backend", self.backend]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     env=self.env, text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     creationflags=flags)
        self._threads = [threading.Thread(target=self._read_out, args=(self.proc,), daemon=True),
                         threading.Thread(target=self._read_err, args=(self.proc,), daemon=True)]
        for t in self._threads:
            t.start()

    def _read_out(self, proc):
        for line in proc.stdout:
            msg = protocol.decode(line)
            if msg is not None:
                self.events.put(msg)
        self.events.put({"event": "exit", "code": proc.poll()})

    def _read_err(self, proc):
        for line in proc.stderr:
            self.stderr_tail.append(line.rstrip())

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self, timeout=3.0):
        if self.proc is None:
            return
        if self.alive():
            try:
                self.send({"cmd": "shutdown"})
                self.proc.wait(timeout)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if self.alive():
            self.proc.kill()
            self.proc.wait(2)

    # -- mensajes
    def send(self, msg):
        if not self.alive():
            raise PFError("el worker de IA no esta en marcha")
        msg = dict(msg)
        msg.setdefault("id", next(self._ids))
        try:
            self.proc.stdin.write(protocol.encode(msg) + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            raise PFError("el worker de IA se ha cerrado")
        return msg["id"]

    def poll(self):
        """Eventos recibidos desde la ultima llamada (no espera)."""
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    def wait_for(self, event, timeout=10.0):
        """Solo para pruebas y utilidades fuera de Blender: espera un evento concreto."""
        import time
        end = time.time() + timeout
        seen = []
        while time.time() < end:
            try:
                msg = self.events.get(timeout=0.1)
            except queue.Empty:
                continue
            seen.append(msg)
            if msg.get("event") == event:
                return msg, seen
        raise TimeoutError("sin evento %r; recibidos: %s" % (event, [m.get("event") for m in seen]))

    def wait_for_any(self, events, timeout=10.0):
        """Como wait_for pero con varios eventos posibles; devuelve el primero que llegue."""
        import time
        end = time.time() + timeout
        seen = []
        while time.time() < end:
            try:
                msg = self.events.get(timeout=0.1)
            except queue.Empty:
                if not self.alive() and self.events.empty():
                    raise PFError("el worker de IA se ha cerrado: " + self.stderr_text(4))
                continue
            seen.append(msg)
            if msg.get("event") in events:
                return msg, seen
            if msg.get("event") == "exit":
                raise PFError("el worker de IA se ha cerrado: " + self.stderr_text(4))
        raise TimeoutError("sin respuesta del worker")

    # -- ordenes
    def hello(self, policy=None):
        return self.send({"cmd": "hello", "cooldown": dict(policy or {})})

    def generate(self, image, out_dir, name, backend=None, params=None, unload_after=False):
        return self.send({"cmd": "generate", "image": str(image), "out_dir": str(out_dir), "name": name,
                          "backend": backend, "params": params or {}, "unload_after": bool(unload_after)})

    def cancel(self):
        self.send({"cmd": "cancel"})

    def stderr_text(self, n=12):
        return "\n".join(list(self.stderr_tail)[-n:])
