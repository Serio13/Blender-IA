"""Sesion de IA dentro de Blender con el worker `fake`: sin bloqueo, normaliza al terminar, respeta la pausa."""
import sys
import time

import bpy
import pytest

from pirate_prop_forge.core import ai_session, meshutil, postprocess
from pirate_prop_forge.core.errors import PFError

POLICY = {"min_seconds": 5, "adaptive": False}


@pytest.fixture
def session(tmp_path):
    ai_session.reset_state()
    ai_session.start(python=sys.executable, backend="fake", policy=POLICY)
    yield ai_session
    ai_session.reset_state()


@pytest.fixture
def image(tmp_path):
    p = tmp_path / "ref.png"
    p.write_bytes(b"png")
    return str(p)


def pump_until(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        ai_session.pump()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_start_reaches_idle(session):
    assert session.STATE.phase == "starting"
    assert session.blocked_reason() == "El motor de IA esta arrancando"
    assert pump_until(lambda: session.STATE.phase == "idle")
    assert session.STATE.backends["fake"]["available"]


def test_generate_is_non_blocking_and_produces_normalized_asset(session, image):
    assert pump_until(lambda: session.STATE.phase == "idle")
    opts = postprocess.Options(category="barril", material="none")
    t = time.time()
    session.generate(image, "Barril_ia_V2", "fake", opts, params={"fake_delay": 0.6})
    assert time.time() - t < 0.3                                   # la llamada vuelve enseguida
    assert session.STATE.phase == "generating" and session.blocked_reason() == "Hay una generacion en curso"
    assert pump_until(lambda: session.STATE.phase == "idle")
    obj = bpy.data.objects["Barril_ia_V2_malla_BAKED"]
    pts = meshutil.world_points(obj)
    assert pts[:, 2].max() - pts[:, 2].min() == pytest.approx(0.85, abs=1e-3)
    assert "Barril_ia_V2_malla_BAKED" in session.STATE.message
    assert bpy.context.view_layer.objects.active == obj


def test_cooldown_blocks_next_generation_with_countdown(session, image):
    assert pump_until(lambda: session.STATE.phase == "idle")
    opts = postprocess.Options(category="barril", material="none")
    session.generate(image, "A", "fake", opts)
    assert pump_until(lambda: session.STATE.phase == "idle")
    reason = session.blocked_reason()
    assert reason and reason.startswith("Enfriando la GPU")
    assert 0 < session.STATE.cooldown_left() <= 5.0
    with pytest.raises(PFError, match="Enfriando"):
        session.generate(image, "B", "fake", opts)
    assert pump_until(lambda: session.blocked_reason() is None, timeout=9)      # termina la cuenta atras


def test_cancel(session, image):
    assert pump_until(lambda: session.STATE.phase == "idle")
    session.generate(image, "A", "fake", postprocess.Options(material="none"), params={"fake_delay": 5.0})
    assert pump_until(lambda: session.STATE.progress > 0)
    session.cancel()
    assert pump_until(lambda: session.STATE.phase == "idle", timeout=6)
    assert "cancelada" in session.STATE.message and "A_malla_BAKED" not in bpy.data.objects


def test_postprocess_failure_is_reported_not_raised(session, image):
    assert pump_until(lambda: session.STATE.phase == "idle")
    session.generate(image, "A", "fake", postprocess.Options(material="ia"))     # sin texturas: falla al normalizar
    assert pump_until(lambda: session.STATE.phase == "idle")
    assert session.STATE.message.startswith("ERROR al normalizar")


def test_worker_crash_sets_error_state(session):
    assert pump_until(lambda: session.STATE.phase == "idle")
    session.STATE.client.proc.kill()
    assert pump_until(lambda: session.STATE.phase == "error")
    assert "cerrado" in session.STATE.message


def test_import_existing_without_ai(tmp_path):
    from test_postprocess import fake_obj
    ai_session.reset_state()
    obj, rep = ai_session.import_existing(fake_obj(tmp_path), "Cofre_x", postprocess.Options(category="cofre", material="none"))
    assert obj.name == "Cofre_x_malla_BAKED" and ai_session.STATE.last_object == obj.name


def test_timer_registered_while_running(session):
    assert bpy.app.timers.is_registered(ai_session._tick)


def test_generated_object_records_model_and_license(session, image):
    assert pump_until(lambda: session.STATE.phase == "idle")
    session.generate(image, "A", "fake", postprocess.Options(material="none"))
    assert pump_until(lambda: session.STATE.phase == "idle")
    obj = bpy.data.objects["A_malla_BAKED"]
    assert obj["pf_source"] == "fake" and obj["pf_commercial_ok"] is False and obj["pf_license"] == "prueba"
