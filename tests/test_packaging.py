import runpy
import sys
import tomllib
import zipfile
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_extension  # noqa: E402


def test_zip_has_manifest_at_root_and_no_caches(tmp_path):
    target = build_extension.build(tmp_path)
    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()
        manifest = tomllib.loads(zf.read("blender_manifest.toml").decode())
    assert target.name == "pirate_prop_forge-%s.zip" % manifest["version"]
    assert "__init__.py" in names and "cli.py" in names and "core/export.py" in names
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
    assert manifest["type"] == "add-on" and manifest["id"] == "pirate_prop_forge"
    assert manifest["license"] and manifest["blender_version_min"]


def test_cli_runs_as_a_blender_script(chest, tmp_path, monkeypatch):
    """Simula: blender.exe -b archivo.blend --python cli.py -- export ..."""
    monkeypatch.setattr(sys, "argv", ["blender", "--", "export", "--target", "*_BAKED",
                                      "--out", str(tmp_path), "--dissolve-deg", "0"])
    runpy.run_path(str(ROOT / "addon" / "pirate_prop_forge" / "cli.py"), run_name="__main__")
    assert (tmp_path / "Cofre_test" / "Cofre_test.fbx").exists()
