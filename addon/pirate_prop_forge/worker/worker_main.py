"""Worker de IA local: lee ordenes JSON por stdin y responde por stdout (ver shared/protocol.py).

Se ejecuta con el Python del entorno de IA, no con el de Blender:
    python worker_main.py [--backend sf3d]
stdout queda reservado al protocolo; todo lo demas (prints de librerias) se redirige a stderr.
"""
import faulthandler
import importlib.util
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

_PROTO_OUT = sys.stdout
sys.stdout = sys.stderr               # que ninguna libreria ensucie el canal del protocolo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _load_shared(name):
    spec = importlib.util.spec_from_file_location("pf_shared_" + name, HERE.parent / "shared" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


protocol = _load_shared("protocol")
cooldown_mod = _load_shared("cooldown")
import backends  # noqa: E402
from backends.base import JobCancelled  # noqa: E402

_lock = threading.Lock()


def send(msg):
    with _lock:
        _PROTO_OUT.write(protocol.encode(msg) + "\n")
        _PROTO_OUT.flush()


class Worker:
    def __init__(self, default_backend=None):
        self.cooldown = cooldown_mod.Cooldown()
        self.default_backend = default_backend
        self.instances = {}
        self.job = None               # id del trabajo en curso o en cola
        self.jobs = queue.Queue()     # los trabajos se ejecutan en el hilo PRINCIPAL (PyTorch/DLL lo prefieren)
        self.cancel_flag = threading.Event()
        self.running = True
        self._cd_thread = None

    # -- utilidades
    def backend(self, name):
        if name not in self.instances:
            self.instances[name] = backends.load(name)
        return self.instances[name]

    def availability(self):
        out = {}
        for name, meta in backends.info().items():
            try:
                ok, why = self.backend(name).available()
            except Exception as exc:                     # noqa: BLE001
                ok, why = False, str(exc)
            out[name] = dict(meta, available=ok, reason=why)
        return out

    def gpu(self):
        return cooldown_mod.read_gpu()

    # -- cooldown
    def _announce_cooldown(self):
        """Emite `cooldown` cada segundo tras un trabajo y `cooldown_done` al terminar."""
        def run():
            while self.running:
                st = self.cooldown.status()
                if st.ready:
                    send({"event": "cooldown_done", "temp": st.temp})
                    return
                send(dict(st.as_dict(), event="cooldown"))
                time.sleep(1.0)
        if self._cd_thread is None or not self._cd_thread.is_alive():
            self._cd_thread = threading.Thread(target=run, daemon=True)
            self._cd_thread.start()

    # -- ordenes
    def handle(self, msg):
        cmd, jid = msg.get("cmd"), msg.get("id")
        if cmd == "hello":
            if isinstance(msg.get("cooldown"), dict):
                self.cooldown.policy = cooldown_mod.Policy.from_dict(msg["cooldown"])
            send({"event": "ready", "id": jid, "protocol": protocol.PROTOCOL_VERSION, "python": sys.version.split()[0],
                  "backends": self.availability(), "gpu": self.gpu(), "cooldown": self.cooldown.status().as_dict()})
        elif cmd == "status":
            send({"event": "status", "id": jid, "busy": self.job is not None, "gpu": self.gpu(),
                  "cooldown": self.cooldown.status().as_dict()})
        elif cmd == "cancel":
            self.cancel_flag.set()
        elif cmd == "shutdown":
            self.running = False
        elif cmd == "generate":
            self.start_job(msg)
        else:
            send(protocol.error(jid, "bad_command", "orden desconocida: %r" % cmd))

    def start_job(self, msg):
        """Valida y encola (hilo lector). El trabajo lo ejecuta el hilo principal."""
        jid = msg.get("id")
        if self.job is not None:
            return send(protocol.error(jid, "busy", "ya hay una generacion en curso"))
        st = self.cooldown.status()
        if not st.ready:
            code = "overheated" if st.reason == "overheated" else "cooldown"
            return send(protocol.error(jid, code, "GPU en pausa de enfriamiento (%.0f s)" % st.remaining,
                                       remaining=st.remaining, temp=st.temp))
        name = msg.get("backend") or self.default_backend or "fake"
        if name not in backends.REGISTRY:
            return send(protocol.error(jid, "bad_backend", "backend desconocido: %s" % name))
        self.cancel_flag.clear()
        self.job = jid
        self.jobs.put((jid, name, msg))

    def run_job(self, jid, name, msg):
        t0 = time.time()
        try:
            be = self.backend(name)
            ok, why = be.available()
            if not ok:
                return send(protocol.error(jid, "unavailable", why))
            image, out_dir = msg.get("image"), msg.get("out_dir")
            if not image or not os.path.isfile(image):
                return send(protocol.error(jid, "bad_input", "imagen no encontrada: %s" % image))
            os.makedirs(out_dir, exist_ok=True)
            stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in (msg.get("name") or "asset"))
            out_path = os.path.join(out_dir, "%s_raw.%s" % (stem, be.output_format))

            last = {"frac": 0.0, "text": "importando PyTorch y el modelo (la primera vez tarda)"}
            t_start = time.time()

            def progress(frac, text=""):
                last["frac"], last["text"] = float(frac), text
                send({"event": "progress", "id": jid, "fraction": round(float(frac), 3), "text": text})

            def heartbeat():            # el panel sigue viendo que el motor esta vivo aunque una fase sea larga
                while not stop_beat.wait(2.0):
                    send({"event": "progress", "id": jid, "fraction": round(last["frac"], 3),
                          "text": "%s (%d s)" % (last["text"], time.time() - t_start)})
            stop_beat = threading.Event()
            threading.Thread(target=heartbeat, daemon=True).start()
            faulthandler.dump_traceback_later(150, repeat=True, file=sys.stderr)   # si se cuelga, deja la pila en el registro
            progress(0.0, last["text"])

            extra = be.generate(image, out_path, msg.get("params") or {}, progress, self.cancel_flag.is_set)
            send({"event": "result", "id": jid, "backend": name, "mesh": out_path, "format": be.output_format,
                  "seconds": round(time.time() - t0, 1), "extra": extra or {}})
        except JobCancelled:
            send(protocol.error(jid, "cancelled", "generacion cancelada"))
        except MemoryError:
            send(protocol.error(jid, "oom", "sin memoria"))
        except Exception as exc:                         # noqa: BLE001
            code = "oom" if "out of memory" in str(exc).lower() else "failed"
            send(protocol.error(jid, code, "%s: %s" % (type(exc).__name__, exc), detail=traceback.format_exc()[-1500:]))
        finally:
            faulthandler.cancel_dump_traceback_later()
            try:
                stop_beat.set()
            except NameError:
                pass
            self.job = None
            if msg.get("unload_after"):
                try:
                    self.backend(name).unload()
                except Exception:                        # noqa: BLE001
                    pass
            self.cooldown.job_finished()                 # la pausa cuenta desde el fin (tambien si fallo)
            self._announce_cooldown()

    def _reader(self):
        for line in sys.stdin:
            msg = protocol.decode(line)
            if msg is None:
                continue
            try:
                self.handle(msg)
            except Exception as exc:                     # noqa: BLE001
                send(protocol.error(msg.get("id"), "internal", "%s: %s" % (type(exc).__name__, exc)))
            if not self.running:
                break
        self.running = False
        self.cancel_flag.set()
        self.jobs.put(None)

    def preload(self):
        """Importa PyTorch y el modelo ANTES de leer ordenes, en el hilo principal y sin otros hilos activos:
        asi la primera generacion arranca al instante y el registro dice donde se atasca si algo falla."""
        faulthandler.dump_traceback_later(120, repeat=True, file=sys.stderr)
        try:
            for name in backends.REGISTRY:
                if name == "fake":
                    continue
                be = self.backend(name)
                if not be.available()[0]:
                    continue
                print("[worker] preparando %s (importar PyTorch la primera vez tarda 1-2 min)..." % name, file=sys.stderr, flush=True)
                t = time.time()
                try:
                    be.preload()
                except Exception as exc:                 # noqa: BLE001
                    print("[worker] %s no se pudo preparar: %s: %s" % (name, type(exc).__name__, exc), file=sys.stderr, flush=True)
                else:
                    print("[worker] %s listo (%.0f s)" % (name, time.time() - t), file=sys.stderr, flush=True)
        finally:
            faulthandler.cancel_dump_traceback_later()

    def loop(self):
        self.preload()
        threading.Thread(target=self._reader, daemon=True).start()
        while self.running or not self.jobs.empty():
            try:
                item = self.jobs.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            self.run_job(*item)
        self.running = False


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None)
    args = ap.parse_args(argv)
    token = os.environ.get("HF_TOKEN")
    if token:
        os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", token)
    Worker(args.backend).loop()


if __name__ == "__main__":
    main()
