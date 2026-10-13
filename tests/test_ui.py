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
