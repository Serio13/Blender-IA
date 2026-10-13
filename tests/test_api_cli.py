import json

import bpy
import pytest

import helpers
from pirate_prop_forge import api, cli
from pirate_prop_forge.core.errors import PFError


def test_lods_output_is_short(chest):
    out = api.lods("*_BAKED", preset="estandar", dissolve_deg=0)
    assert out.count("\n") == 0
    assert out.startswith("Cofre_test: LOD0 14904 | LOD1 ") and "LOD2" in out
    assert len(out) < 100


def test_export_summary_and_files(chest, tmp_path):
    out = api.export("*_BAKED", out_dir=str(tmp_path), dissolve_deg=0)
    assert out.splitlines()[0].startswith("Cofre_test: LOD0 14904")
    assert "[FBX+BLEND +3 tex]" in out
    assert (tmp_path / "Cofre_test" / "Cofre_test.fbx").exists()


def test_export_reuses_existing_lods_unless_regenerate(chest, tmp_path):
    api.lods("*_BAKED", tris=(4000, 900), dissolve_deg=0)
    out = api.export("*_BAKED", out_dir=str(tmp_path), formats=("fbx",))
    assert "LOD1 4" in out  # LOD1 ~4000 triangulos, no el 35 % del preset
    out2 = api.export("*_BAKED", out_dir=str(tmp_path), formats=("fbx",), regenerate=True, dissolve_deg=0)
    assert "LOD1 5" in out2


def test_clean(chest):
    api.lods("*_BAKED", dissolve_deg=0)
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
    assert cli.main(["lods", "--target", "*_BAKED", "--ratios", "0.4,0.1", "--dissolve-deg", "0"]) == 0
    assert "LOD1" in capsys.readouterr().out
    assert cli.main(["export", "--target", "*_BAKED", "--out", str(tmp_path), "--no-blend", "--collider", "none",
                     "--regenerate", "--tris", "4000,1000", "--dissolve-deg", "0"]) == 0
    assert (tmp_path / "Cofre_test" / "Cofre_test.fbx").exists()
    assert not (tmp_path / "Cofre_test" / "Cofre_test.blend").exists()
    assert cli.main(["profile", "--out", str(tmp_path / "p.json")]) == 0
    assert json.loads((tmp_path / "p.json").read_text())["assets"] == 1
    assert cli.main(["clean", "--target", "*_BAKED"]) == 0


def test_cli_reports_errors_with_exit_code(capsys):
    assert cli.main(["lods", "--target", "no_existe"]) == 1
    assert capsys.readouterr().out.startswith("ERROR:")


def test_cli_drop_uv2(chest, tmp_path):
    cli.main(["lods", "--target", "*_BAKED", "--drop-uv2", "--dissolve-deg", "0"])
    lod = next(o for o in bpy.data.objects if o.get("pf_lod") == 1)
    assert len(lod.data.uv_layers) == 1
