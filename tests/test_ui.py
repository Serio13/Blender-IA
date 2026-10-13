import bpy
import pytest

import pirate_prop_forge as pf


@pytest.fixture
def registered():
    pf.register()
    yield
    pf.unregister()


def _select(*objs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def test_register_unregister_roundtrip():
    pf.register()
    assert hasattr(bpy.types.Scene, "pf")
    pf.unregister()
    assert not hasattr(bpy.types.Scene, "pf")
    pf.register()
    pf.unregister()


def test_operators_work_on_selection(chest, registered, tmp_path):
    base, lid, _ = chest
    _select(base, lid)
    settings = bpy.context.scene.pf
    settings.dissolve_deg = 0.0
    assert bpy.ops.pf.lods() == {"FINISHED"}
    assert len([o for o in bpy.data.objects if o.get("pf_lod")]) == 4
    settings.out_dir = str(tmp_path)
    settings.collider = "mesh"
    assert bpy.ops.pf.export() == {"FINISHED"}
    assert (tmp_path / "Cofre_test" / "Cofre_test.fbx").exists()
    assert bpy.ops.pf.clean_lods() == {"FINISHED"}
    assert not [o for o in bpy.data.objects if o.get("pf_lod")]


def test_operator_reports_error_without_selection(registered):
    _select_none = [o.select_set(False) for o in bpy.context.view_layer.objects]
    with pytest.raises(RuntimeError, match="sin objetivos"):
        bpy.ops.pf.lods()


def test_panels_exist(registered):
    for cls in ("PF_PT_main", "PF_PT_lods", "PF_PT_export"):
        assert hasattr(bpy.types, cls)


def test_last_result_is_stored_and_drawable(chest, registered):
    base, lid, _ = chest
    _select(base, lid)
    bpy.context.scene.pf.dissolve_deg = 0.0
    bpy.ops.pf.lods()
    text = bpy.context.scene.pf.last_result
    assert text.startswith("Cofre_test: LOD0")
    from pirate_prop_forge.ui import panel

    class FakeBox:
        def __init__(self):
            self.labels = []

        def label(self, text=""):
            self.labels.append(text)

        def box(self):
            return self

    fake = FakeBox()
    panel.draw_result(fake, "x" * 100 + "\n" + text)
    assert fake.labels and all(len(t) <= 42 for t in fake.labels)


def test_error_is_stored_too(registered):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    with pytest.raises(RuntimeError):
        bpy.ops.pf.lods()
    assert bpy.context.scene.pf.last_result.startswith("ERROR:")


def test_check_operator_fills_the_panel_result(chest, registered):
    base, lid, _ = chest
    _select(base, lid)
    assert bpy.ops.pf.check() == {"FINISHED"}
    text = bpy.context.scene.pf.last_result
    assert text.startswith("Prop Forge v") and "BaseMap" in text
