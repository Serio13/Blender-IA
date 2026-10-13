import importlib.util
from pathlib import Path

import pytest

from pirate_prop_forge.shared import cooldown, protocol
from pirate_prop_forge.shared.cooldown import Cooldown, Policy


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class FakeGpu:
    def __init__(self, temp=60.0):
        self.temp = temp
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return None if self.temp is None else {"temp": self.temp}


def make(temp=60.0, **policy):
    clock, gpu = Clock(), FakeGpu(temp)
    return Cooldown(Policy(**policy), clock=clock, gpu=gpu, cache_seconds=0.0), clock, gpu


def test_ready_before_any_job():
    cd, _, _ = make()
    assert cd.status().ready


def test_fixed_pause_counts_down_and_blocks():
    cd, clock, _ = make(min_seconds=10)
    cd.job_finished()
    s = cd.status()
    assert not s.ready and s.reason == "fixed" and s.remaining == pytest.approx(10.0)
    clock.advance(4)
    assert cd.status().remaining == pytest.approx(6.0)
    clock.advance(6.01)
    assert cd.status().ready


def test_pause_floor_is_5_seconds_even_if_configured_lower():
    cd, clock, _ = make(min_seconds=0)
    cd.job_finished()
    assert cd.status().remaining == pytest.approx(5.0)


def test_adaptive_waits_for_temperature_then_resumes():
    cd, clock, gpu = make(min_seconds=5, resume_temp=70, max_wait=60)
    cd.job_finished()
    gpu.temp = 78.0
    clock.advance(10)
    s = cd.status()
    assert not s.ready and s.reason == "temp" and s.temp == 78.0
    gpu.temp = 69.0
    assert cd.status().ready


def test_adaptive_gives_up_at_max_wait():
    cd, clock, gpu = make(min_seconds=5, resume_temp=70, max_wait=30)
    cd.job_finished()
    gpu.temp = 80.0
    clock.advance(31)
    assert cd.status().ready


def test_non_adaptive_ignores_temperature():
    cd, clock, gpu = make(min_seconds=5, adaptive=False)
    cd.job_finished()
    gpu.temp = 80.0
    clock.advance(6)
    assert cd.status().ready


def test_overheated_blocks_even_without_previous_job_until_it_cools():
    cd, clock, gpu = make(abort_temp=85, resume_temp=72, temp=88.0)
    s = cd.status()
    assert not s.ready and s.reason == "overheated"
    gpu.temp = 71.0
    assert cd.status().ready


def test_missing_gpu_reading_falls_back_to_fixed_pause():
    cd, clock, gpu = make(temp=None, min_seconds=8)
    cd.job_finished()
    assert cd.status().reason == "fixed" and cd.status().temp is None
    clock.advance(9)
    assert cd.status().ready


def test_gpu_reads_are_cached():
    clock, gpu = Clock(), FakeGpu(60.0)
    cd = Cooldown(Policy(), clock=clock, gpu=gpu, cache_seconds=1.0)
    for _ in range(5):
        cd.status()
    assert gpu.calls == 1
    clock.advance(1.5)
    cd.status()
    assert gpu.calls == 2


def test_gpu_exception_does_not_break_the_guard():
    def boom():
        raise RuntimeError("driver")
    cd = Cooldown(Policy(), clock=Clock(), gpu=boom)
    assert cd.status().ready


def test_parse_nvidia_smi():
    assert cooldown.parse_nvidia_smi("67, 98, 231.47, 8412, 11264\n") == {
        "temp": 67.0, "util": 98.0, "power": 231.47, "mem_used": 8412.0, "mem_total": 11264.0}
    assert cooldown.parse_nvidia_smi("55, 3, [N/A], 900, 11264")["power"] is None
    assert cooldown.parse_nvidia_smi("") is None and cooldown.parse_nvidia_smi("garbage") is None


def test_read_gpu_handles_missing_binary_and_failure():
    def missing(*a, **k):
        raise FileNotFoundError("nvidia-smi")

    class R:
        returncode, stdout = 9, ""
    assert cooldown.read_gpu(missing) is None
    assert cooldown.read_gpu(lambda *a, **k: R()) is None


def test_policy_from_dict_normalizes():
    p = Policy.from_dict({"min_seconds": 1, "resume_temp": 80, "abort_temp": 70, "bogus": 1})
    assert p.min_seconds == 5.0 and p.abort_temp > p.resume_temp


def test_protocol_roundtrip_and_bad_lines():
    msg = {"id": 3, "cmd": "generate", "image": "C:\\ñandú\\a.png"}
    assert protocol.decode(protocol.encode(msg)) == msg
    assert protocol.decode("") is None and protocol.decode("not json") is None and protocol.decode("[1]") is None
    assert protocol.error(1, "cooling", "espera", remaining=3)["code"] == "cooling"


def test_shared_modules_load_without_blender_or_package_context():
    """El worker los carga por ruta, en un Python sin bpy ni el paquete del plugin."""
    path = Path(cooldown.__file__)
    spec = importlib.util.spec_from_file_location("standalone_cooldown", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.Cooldown and not any(name.startswith(("bpy", "bmesh")) for name in vars(mod))
    assert "import bpy" not in path.read_text(encoding="utf-8")
