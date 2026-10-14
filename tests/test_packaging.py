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


def test_single_version_everywhere(tmp_path):
    import importlib
    version = importlib.import_module("pirate_prop_forge.core.version").VERSION
    manifest = tomllib.loads((ROOT / "addon" / "pirate_prop_forge" / "blender_manifest.toml").read_text(encoding="utf-8"))
    assert manifest["version"] == version
    import pirate_prop_forge
    assert ".".join(str(n) for n in pirate_prop_forge.bl_info["version"]) == version
    assert build_extension.build(tmp_path).name == "pirate_prop_forge-%s.zip" % version


def test_zip_ships_the_worker_and_it_runs_from_the_packaged_layout(tmp_path):
    import subprocess
    target = build_extension.build(tmp_path)
    with zipfile.ZipFile(target) as zf:
        names = set(zf.namelist())
        for needed in ("worker/worker_main.py", "worker/doctor.py", "worker/install_ia.ps1", "worker/instalar_ia.bat",
                       "worker/backends/sf3d.py", "worker/backends/fake.py", "shared/cooldown.py", "shared/protocol.py",
                       "shared/licenses.py"):
            assert needed in names, needed
        dest = tmp_path / "ext" / "pirate_prop_forge"
        zf.extractall(dest)
    out = subprocess.run([sys.executable, str(dest / "worker" / "worker_main.py")], input='{"id":1,"cmd":"hello"}\n{"cmd":"shutdown"}\n',
                         capture_output=True, text=True, timeout=30)
    assert '"event":"ready"' in out.stdout, out.stderr
    doc = subprocess.run([sys.executable, str(dest / "worker" / "doctor.py")], capture_output=True, text=True, timeout=60)
    assert "VEREDICTO" in doc.stdout


def test_installer_banner_matches_plugin_version():
    """El instalador imprime su version: asi se ve si se ejecuta una copia antigua."""
    from pirate_prop_forge.core.version import VERSION
    ps1 = (ROOT / "addon" / "pirate_prop_forge" / "worker" / "install_ia.ps1").read_text(encoding="utf-8")
    assert "version %s" % VERSION in ps1
    assert "--no-build-isolation" in ps1
