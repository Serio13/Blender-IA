import sys
import time

import bpy
import pytest

import pirate_prop_forge as pf
from pirate_prop_forge.core import ai_client, ai_session
from pirate_prop_forge.ui import panel, prefs as prefs_mod


@pytest.fixture
def registered(monkeypatch):
    monkeypatch.setattr(ai_client, "find_python", lambda configured="": sys.executable)
    ai_session.reset_state()
    pf.register()
    yield
    ai_session.reset_state()
    pf.unregister()


class Rec:
    """Capa de dibujo falsa: registra las llamadas y devuelve subcapas."""
    def __init__(self, log=None):
        self.log = log if log is not None else []
        self.enabled = True
        self.scale_y = 1.0

    def __getattr__(self, name):
        def call(*a, **kw):
            self.log.append((name, a, kw))
            return Rec(self.log)
        return call


class FakePanel:
    def __init__(self):
        self.layout = Rec()


def draw(context):
    p = FakePanel()
    panel.PF_PT_ai.draw(p, context)
    return p.layout.log


def pump_until(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        ai_session.pump()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_panel_draws_in_every_state(registered):
    ctx = bpy.context
    pf_ = ctx.scene.pf
    pf_.ai_material = "madera"
    pf_.ai_budget = "manual"
    assert any(c[0] == "operator" and c[1][0] == "pf.ai_start" for c in draw(ctx))
    ai_session.STATE.doctor_text = "OK algo"
    bpy.ops.pf.ai_start()
    assert pump_until(lambda: ai_session.STATE.phase == "idle")
    ai_session.STATE.phase, ai_session.STATE.progress = "generating", 0.4
    assert any(c[0] == "progress" for c in draw(ctx))
    ai_session.STATE.phase = "idle"
    ai_session.STATE.cooldown_until = time.monotonic() + 7
    log = draw(ctx)
    assert any(c[0] == "progress" and "Enfriando GPU" in c[2]["text"] for c in log)


def test_generate_operator_end_to_end(registered, tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(b"x")
    s = bpy.context.scene.pf
    s.ai_image, s.ai_name, s.ai_backend, s.ai_category, s.ai_material = str(img), "Barril_ia_V2", "fake", "barril", "none"
    prefs_mod.get = lambda context=None: type("P", (), {"commercial_only": False, "unload_after": False,
                                                        "worker_python": "", "hf_token": "", "policy": lambda self: {"min_seconds": 5, "adaptive": False}})()
    try:
        assert bpy.ops.pf.ai_start() == {"FINISHED"}
        assert pump_until(lambda: ai_session.STATE.phase == "idle")
        assert bpy.ops.pf.ai_generate() == {"FINISHED"}
        assert pump_until(lambda: "Barril_ia_V2_malla_BAKED" in bpy.data.objects)
        assert pump_until(lambda: ai_session.STATE.phase == "idle")
        with pytest.raises(RuntimeError, match="Enfriando"):
            bpy.ops.pf.ai_generate()
    finally:
        import importlib
        importlib.reload(prefs_mod)


def test_test_only_model_is_blocked_in_commercial_mode(registered, tmp_path, monkeypatch):
    img = tmp_path / "r.png"
    img.write_bytes(b"x")
    s = bpy.context.scene.pf
    s.ai_image, s.ai_backend = str(img), "fake"
    monkeypatch.setattr("pirate_prop_forge.ui.operators.prefs_mod.get",
                        lambda context=None: type("P", (), {"commercial_only": True, "unload_after": False})())
    with pytest.raises(RuntimeError, match="solo de prueba"):
        bpy.ops.pf.ai_generate()


def test_import_operator_without_ai(registered, tmp_path):
    from test_postprocess import fake_obj
    s = bpy.context.scene.pf
    s.ai_mesh, s.ai_name, s.ai_category, s.ai_material = str(fake_obj(tmp_path)), "Cofre_x", "cofre", "none"
    assert bpy.ops.pf.ai_import() == {"FINISHED"}
    assert "Cofre_x_malla_BAKED" in bpy.data.objects


def test_generate_without_worker_fails_clearly(registered, tmp_path):
    s = bpy.context.scene.pf
    s.ai_image, s.ai_backend = str(tmp_path / "a.png"), "sf3d"
    with pytest.raises(RuntimeError, match="no esta en marcha"):
        bpy.ops.pf.ai_generate()


def test_policy_is_clamped_by_worker_not_by_ui():
    p = prefs_mod.PF_Preferences
    assert p.__annotations__["cooldown_seconds"].keywords["min"] == 5.0
    assert p.__annotations__["cooldown_seconds"].keywords["max"] == 15.0
