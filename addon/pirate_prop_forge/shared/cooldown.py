"""Proteccion termica: pausa obligatoria entre generaciones y lectura de la GPU con nvidia-smi.

Sin dependencias (ni bpy ni torch): lo cargan el plugin (cuenta atras en el panel) y el worker (que es quien
impone la pausa de verdad, aunque alguien salte la interfaz).
"""
import subprocess
import time
from dataclasses import dataclass

MIN_SECONDS_FLOOR = 5.0      # la pausa fija nunca baja de aqui
MIN_SECONDS_CEIL = 300.0


@dataclass
class Policy:
    min_seconds: float = 10.0     # pausa fija obligatoria entre generaciones (recomendado 5-15 s)
    adaptive: bool = True         # ademas, esperar a que la GPU baje de resume_temp
    resume_temp: float = 72.0     # grados C a los que se puede reanudar
    abort_temp: float = 85.0      # por encima, no se acepta trabajo nuevo
    max_wait: float = 60.0        # tope de la espera adaptativa (segundos desde el fin del trabajo)

    def normalized(self):
        self.min_seconds = max(MIN_SECONDS_FLOOR, min(MIN_SECONDS_CEIL, float(self.min_seconds)))
        self.resume_temp = float(self.resume_temp)
        self.abort_temp = max(float(self.abort_temp), self.resume_temp + 1)
        self.max_wait = max(self.min_seconds, float(self.max_wait))
        return self

    @classmethod
    def from_dict(cls, data):
        known = {k: data[k] for k in ("min_seconds", "adaptive", "resume_temp", "abort_temp", "max_wait") if k in data}
        return cls(**known).normalized()


@dataclass
class Status:
    ready: bool
    remaining: float              # segundos de espera estimados (0 si ready)
    temp: float                   # grados C (None si no hay lectura)
    reason: str                   # None | "fixed" | "temp" | "overheated"

    def as_dict(self):
        return {"ready": self.ready, "remaining": round(self.remaining, 1), "temp": self.temp, "reason": self.reason}


def parse_nvidia_smi(text):
    """'temp, util, power, mem_used, mem_total' (csv sin cabecera ni unidades) -> dict o None."""
    for line in (text or "").strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue

        def num(x):
            try:
                return float(x)
            except ValueError:
                return None            # "[N/A]", "[Not Supported]"...

        temp, util, power, used, total = (num(p) for p in parts[:5])
        return {"temp": temp, "util": util, "power": power, "mem_used": used, "mem_total": total}
    return None


def read_gpu(runner=subprocess.run):
    """Lee la primera GPU NVIDIA. None si no hay nvidia-smi o falla."""
    try:
        out = runner(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,power.draw,memory.used,memory.total",
                      "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return parse_nvidia_smi(out.stdout)


class Cooldown:
    """Decide cuando se puede lanzar otra generacion.

    Reglas: (1) pausa fija desde el fin del trabajo anterior; (2) si es adaptativa y la GPU esta por encima de
    resume_temp, se espera a que baje (hasta max_wait); (3) si la GPU esta a abort_temp o mas, se bloquea
    hasta que baje de resume_temp, tambien sin trabajo previo.
    """

    def __init__(self, policy=None, clock=time.monotonic, gpu=read_gpu, cache_seconds=1.0):
        self.policy = (policy or Policy()).normalized()
        self.clock = clock
        self.gpu = gpu
        self.cache_seconds = cache_seconds
        self._t_end = None
        self._cached = (None, None)       # (instante, lectura)

    def job_finished(self):
        self._t_end = self.clock()

    def reset(self):
        self._t_end = None

    def _temp(self):
        now = self.clock()
        t, reading = self._cached
        if t is None or now - t >= self.cache_seconds:
            try:
                reading = self.gpu()
            except Exception:
                reading = None
            self._cached = (now, reading)
        return None if not reading else reading.get("temp")

    def status(self):
        p = self.policy
        temp = self._temp()
        hot = temp is not None and temp >= p.abort_temp
        if self._t_end is None:
            if hot:
                return Status(False, 1.0, temp, "overheated")
            return Status(True, 0.0, temp, None)
        elapsed = self.clock() - self._t_end
        fixed_left = max(0.0, p.min_seconds - elapsed)
        if hot:
            return Status(False, max(fixed_left, 1.0), temp, "overheated")
        if p.adaptive and temp is not None and temp > p.resume_temp and elapsed < p.max_wait:
            return Status(False, max(fixed_left, 1.0), temp, "temp")
        if fixed_left > 0:
            return Status(False, fixed_left, temp, "fixed")
        return Status(True, 0.0, temp, None)
