import bpy

import helpers
from pirate_prop_forge import api
from pirate_prop_forge.core import profile


def _scene_with_assets():
    for i in range(6):
        mat = helpers.make_material("Barril_%d" % i)
        helpers.make_barrel("Barril_%d_malla_BAKED" % i, loc=(i, 0, 0), material=mat, segs=24 + i, rings=16)
    helpers.make_chest()
    # referencia de escala: coleccion REF_pirata con un cuerpo de 1.62 m
    col = bpy.data.collections.new("REF_pirata")
    bpy.context.scene.collection.children.link(col)
    ref = helpers.make_detailed_box("Cuerpo", dims=(0.5, 0.3, 1.62), origin_offset=(0, 0, -0.81), cuts=1)
    bpy.context.scene.collection.objects.unlink(ref)
    col.objects.link(ref)


def test_profile_is_compact_and_informative():
    _scene_with_assets()
    prof = profile.build_profile()
    assert prof["assets"] == 7
    assert prof["ref_height_m"] == 1.62
    assert prof["families"]["Barril"]["n"] == 6 and prof["families"]["Cofre"]["n"] == 1
    assert prof["families"]["Cofre"]["tex_px"] == [64] and prof["families"]["Cofre"]["uv"] == [2]
    assert set(prof["part_labels"]) >= {"base", "tapa"}
    import json
    assert len(json.dumps(prof, separators=(",", ":"))) < 1500
    assert len(profile.summarize(prof).splitlines()) <= 6


def test_reference_and_lod_objects_are_excluded():
    _scene_with_assets()
    api.lods("*_BAKED", dissolve_deg=0)
    prof = profile.build_profile()
    assert prof["assets"] == 7  # ni Cuerpo (REF_pirata) ni los LODs generados cuentan


def test_api_profile_writes_json(tmp_path):
    _scene_with_assets()
    text = api.profile(str(tmp_path / "style_profile.json"))
    assert "bytes" in text and (tmp_path / "style_profile.json").exists()


def test_empty_scene():
    assert profile.build_profile()["assets"] == 0
