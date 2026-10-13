import json

import bpy
import pytest

import helpers
from pirate_prop_forge import api, cli
from pirate_prop_forge.core.errors import PFError


def test_lods_output_is_short(chest):
    out = api.lods("*_BAKED", preset="estandar", dissolve_deg=0, strict=False)
    assert out.count("\n") == 0
    assert out.startswith("Cofre_test: LOD0 14904 | LOD1 ") and "LOD2" in out
    assert len(out) < 250  # una linea; los avisos de calidad solo aparecen si hay problema


def test_export_summary_and_files(chest, tmp_path):
    out = api.export("*_BAKED", out_dir=str(tmp_path), dissolve_deg=0, strict=False)
    assert out.splitlines()[0].startswith("Cofre_test: LOD0 14904")
    assert "[FBX+BLEND +3 tex]" in out and "pivote=base" in out
    assert (tmp_path / "Cofre_test" / "Cofre_test.fbx").exists()


def test_export_reuses_existing_lods_unless_regenerate(chest, tmp_path):
    api.lods("*_BAKED", tris=(4000, 900), dissolve_deg=0, strict=False)
    out = api.export("*_BAKED", out_dir=str(tmp_path), formats=("fbx",))
    assert "LOD1 4" in out  # LOD1 ~4000 triangulos, no el 35 % del preset
    out2 = api.export("*_BAKED", out_dir=str(tmp_path), formats=("fbx",), regenerate=True, dissolve_deg=0, strict=False)
    assert "LOD1 5" in out2


def test_clean(chest):
    api.lods("*_BAKED", dissolve_deg=0, strict=False)
    assert "Cofre_test=" in api.clean("*_BAKED")
    assert not [o for o in bpy.data.objects if o.get("pf_lod")]


def test_errors_are_short_messages(chest, tmp_path):
    with pytest.raises(PFError):
        api.export("*_BAKED")
    with pytest.raises(PFError):
        api.lods("*_BAKED", cosa_rara=1)
    with pytest.raises(PFError):
        api.export("*_BAKED", out_dir=str(tmp_path), collider="x")


def test_cli_lods_export_profile_clean(chest, tmp_path, capsys):
    assert cli.main(["lods", "--target", "*_BAKED", "--ratios", "0.4,0.1", "--dissolve-deg", "0", "--no-strict"]) == 0
    assert "LOD1" in capsys.readouterr().out
    assert cli.main(["export", "--target", "*_BAKED", "--out", str(tmp_path), "--no-blend", "--collider", "none",
                     "--regenerate", "--tris", "4000,1000", "--dissolve-deg", "0", "--no-strict"]) == 0
    assert (tmp_path / "Cofre_test" / "Cofre_test.fbx").exists()
    assert not (tmp_path / "Cofre_test" / "Source~").exists()
    assert cli.main(["profile", "--out", str(tmp_path / "p.json")]) == 0
    assert json.loads((tmp_path / "p.json").read_text())["assets"] == 1
    assert cli.main(["clean", "--target", "*_BAKED"]) == 0


def test_cli_reports_errors_with_exit_code(capsys):
    assert cli.main(["lods", "--target", "no_existe"]) == 1
    assert capsys.readouterr().out.startswith("ERROR:")


def test_cli_drop_uv2(chest, tmp_path):
    cli.main(["lods", "--target", "*_BAKED", "--drop-uv2", "--dissolve-deg", "0", "--no-strict"])
    lod = next(o for o in bpy.data.objects if o.get("pf_lod") == 1)
    assert len(lod.data.uv_layers) == 1


def test_check_reports_recognised_textures(chest):
    out = api.check("*_BAKED")
    lines = out.splitlines()
    assert lines[0].startswith("Prop Forge v")
    assert "Cofre_test: 2 pieza(s), 14904 tris" in lines[1]
    assert "BaseMap 64" in lines[1] and "Normal 64" in lines[1] and "Metallic 64" in lines[1]
    assert "FALTA" not in lines[1]


def test_check_flags_missing_and_unknown_textures():
    mat = bpy.data.materials.new("TXB_Raro")
    for name in ("TX_Raro_Metallic", "TX_Raro_Cosa"):
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = helpers.make_image(name, 8, "metal")
    helpers.make_detailed_box("Raro_malla_BAKED", cuts=2, material=mat)
    line = api.check("Raro_malla_BAKED").splitlines()[1]
    assert "FALTA: BaseMap, Normal" in line and "sin reconocer: TX_Raro_Cosa" in line
    helpers.make_detailed_box("Nada_malla_BAKED", cuts=2)
    assert "SIN TEXTURAS" in api.check("Nada_malla_BAKED")


def test_check_via_cli_and_operator(chest, capsys):
    assert cli.main(["check", "--target", "*_BAKED"]) == 0
    assert "Prop Forge v" in capsys.readouterr().out
    assert api.version() == __import__("pirate_prop_forge.core.version", fromlist=["VERSION"]).VERSION
