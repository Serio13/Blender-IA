"""Worker real en un proceso aparte con el backend `fake`: protocolo, cancelacion, pausa de enfriamiento."""
import sys
import time

import pytest

from pirate_prop_forge.core import ai_client
from pirate_prop_forge.core.errors import PFError

FAST = {"min_seconds": 5, "adaptive": False}


@pytest.fixture
def client(tmp_path):
    cli = ai_client.AIClient(sys.executable, backend="fake")
    cli.start()
    yield cli
    cli.stop()


@pytest.fixture
def image(tmp_path):
    p = tmp_path / "ref.png"
    p.write_bytes(b"png")
    return p


def test_hello_lists_backends_and_licenses(client):
    client.hello(FAST)
    ready, _ = client.wait_for("ready")
    assert set(ready["backends"]) == {"fake", "sf3d", "triposr"}
    assert ready["backends"]["fake"]["available"] is True
    assert ready["backends"]["sf3d"]["available"] is False                 # sin torch en el entorno de pruebas
    assert "Stability" in ready["backends"]["sf3d"]["license"] and ready["backends"]["triposr"]["license"] == "MIT"
    assert ready["backends"]["fake"]["commercial_ok"] is False


def test_generate_job_reports_progress_and_result(client, image, tmp_path):
    client.hello(FAST)
    client.wait_for("ready")
    jid = client.generate(image, tmp_path / "out", "Barril")
    res, seen = client.wait_for("result")
    assert res["id"] == jid and res["mesh"].endswith("Barril_raw.obj")
    assert [m["fraction"] for m in seen if m["event"] == "progress"][-1] == 1.0
    assert (tmp_path / "out" / "Barril_raw.obj").is_file()


def test_second_job_is_refused_during_cooldown_then_accepted(client, image, tmp_path):
    client.hello({"min_seconds": 5, "adaptive": False})
    client.wait_for("ready")
    client.generate(image, tmp_path / "o", "A")
    client.wait_for("result")
    client.generate(image, tmp_path / "o", "B")                             # demasiado pronto
    err, _ = client.wait_for("error")
    assert err["code"] == "cooldown" and 0 < err["remaining"] <= 5
    done, seen = client.wait_for("cooldown_done", timeout=9)                # la pausa de 5 s termina
    cds = [m for m in seen if m["event"] == "cooldown"]
    assert cds and cds[0]["reason"] == "fixed" and cds[0]["remaining"] <= 5
    jid = client.generate(image, tmp_path / "o", "C")
    res, _ = client.wait_for("result")
    assert res["id"] == jid


def test_cooldown_floor_cannot_be_bypassed_by_the_client(client, image, tmp_path):
    client.hello({"min_seconds": 0, "adaptive": False})                    # el worker lo sube a 5 s
    client.wait_for("ready")
    client.generate(image, tmp_path / "o", "A")
    client.wait_for("result")
    client.generate(image, tmp_path / "o", "B")
    err, _ = client.wait_for("error")
    assert err["code"] == "cooldown"


def test_cancel_stops_the_job(client, image, tmp_path):
    client.hello(FAST)
    client.wait_for("ready")
    client.send({"cmd": "generate", "image": str(image), "out_dir": str(tmp_path / "o"), "name": "A", "backend": "fake",
                 "params": {"fake_delay": 5.0}})
    client.wait_for("progress")
    client.cancel()
    err, _ = client.wait_for("error", timeout=6)
    assert err["code"] == "cancelled"


def test_busy_and_bad_input(client, image, tmp_path):
    client.hello(FAST)
    client.wait_for("ready")
    client.send({"cmd": "generate", "image": str(tmp_path / "missing.png"), "out_dir": str(tmp_path), "name": "A"})
    err, _ = client.wait_for("error")
    assert err["code"] == "bad_input"
    client.send({"cmd": "generate", "image": str(image), "out_dir": str(tmp_path), "name": "A", "backend": "nope"})
    assert client.wait_for("error", timeout=9)[0]["code"] in ("bad_backend", "cooldown")


def test_unavailable_backend_reports_reason(client, image, tmp_path):
    client.hello(FAST)
    client.wait_for("ready")
    client.generate(image, tmp_path / "o", "A", backend="sf3d")
    err, _ = client.wait_for("error")
    assert err["code"] == "unavailable" and "instalador" in err["message"]


def test_client_never_blocks(client):
    t = time.time()
    client.poll()
    client.hello(FAST)
    client.poll()
    assert time.time() - t < 0.2


def test_missing_python_gives_actionable_error(tmp_path):
    with pytest.raises(PFError, match="instalar_ia"):
        ai_client.AIClient(str(tmp_path / "no_python.exe"))


def test_worker_exit_is_reported(client):
    client.send({"cmd": "shutdown"})
    ev, _ = client.wait_for("exit")
    assert ev["code"] == 0



def test_commands_stay_responsive_while_a_job_runs(client, image, tmp_path):
    """Los trabajos corren en el hilo principal; el hilo lector sigue atendiendo `status`."""
    client.hello(FAST)
    client.wait_for("ready")
    client.send({"cmd": "generate", "image": str(image), "out_dir": str(tmp_path / "o"), "name": "A", "backend": "fake",
                 "params": {"fake_delay": 3.0}})
    client.wait_for("progress")
    client.send({"cmd": "status"})
    st, _ = client.wait_for("status", timeout=1.5)
    assert st["busy"] is True
    client.wait_for("result", timeout=8)


def test_preload_runs_before_the_worker_reads_commands(tmp_path):
    """El worker prepara los modelos reales (importar PyTorch) antes de aceptar ordenes."""
    import subprocess
    probe = tmp_path / "sitecustomize_probe"
    src = (ai_client.WORKER_SCRIPT).read_text(encoding="utf-8")
    assert "def preload(self)" in src and src.index("self.preload()") < src.index("threading.Thread(target=self._reader")
