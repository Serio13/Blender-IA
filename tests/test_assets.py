import bpy
import pytest

import helpers
from pirate_prop_forge.core import assets, naming
from pirate_prop_forge.core.errors import PFError


def test_naming_helpers():
    assert naming.strip_baked("Cofre_V2_base_BAKED.001") == "Cofre_V2_base"
    assert naming.split_part("Cofre_V2_tapa") == ("Cofre_V2", "tapa")
    assert naming.split_part("Llave_comun_V2") == ("Llave_comun_V2", "")
    assert naming.family("Barril_polvora_V2") == "Barril"


def test_groups_parts_into_one_asset(chest):
    base, lid, _ = chest
    (asset,) = assets.find_assets([base.name, lid.name])
    assert asset.name == "Cofre_test"
    assert [p.label for p in asset.parts] == ["base", "tapa"]
    assert asset.anchor is base


def test_single_mesh_and_labels():
    mat = helpers.make_material("Barril_x")
    barrel = helpers.make_barrel("Barril_x_malla_BAKED", material=mat)
    (asset,) = assets.find_assets([barrel.name])
    assert asset.name == "Barril_x" and asset.single


def test_parent_empty_defines_asset_and_anchor():
    root = bpy.data.objects.new("Cofre_comun", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (2, 0, 0)
    a = helpers.make_detailed_box("Cofre_comun_base", parent=root, loc=(2, 0, 0))
    b = helpers.make_detailed_box("Cofre_comun_tapa", parent=root, loc=(2, 0, 0.3))
    (asset,) = assets.find_assets([a.name, b.name])
    assert asset.name == "Cofre_comun" and asset.anchor is root


def test_baked_wins_over_unbaked():
    helpers.make_detailed_box("Caja_V2_malla")
    helpers.make_detailed_box("Caja_V2_malla_BAKED")
    (asset,) = assets.find_assets("Caja_V2_*")
    assert [p.obj.name for p in asset.parts] == ["Caja_V2_malla_BAKED"]


def test_ucx_and_col_are_ignored():
    helpers.make_detailed_box("Caja_malla")
    helpers.make_detailed_box("UCX_Caja")
    helpers.make_detailed_box("Caja_COL")
    (asset,) = assets.find_assets("*")
    assert asset.name == "Caja"


def test_collection_pattern_and_errors():
    col = bpy.data.collections.new("PROPS")
    bpy.context.scene.collection.children.link(col)
    obj = helpers.make_detailed_box("Mesa_malla")
    bpy.context.scene.collection.objects.unlink(obj)
    col.objects.link(obj)
    assert assets.find_assets("PROPS")[0].name == "Mesa"
    with pytest.raises(PFError):
        assets.find_assets("no_existe")
    with pytest.raises(PFError):
        assets.find_assets("zzz*")


def test_name_override_needs_single_asset():
    helpers.make_detailed_box("A_malla")
    helpers.make_detailed_box("B_malla")
    with pytest.raises(PFError):
        assets.find_assets("*_malla", name="X")
    assert assets.find_assets("A_malla", name="X")[0].name == "X"
