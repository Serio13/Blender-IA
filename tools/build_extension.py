"""Genera dist/pirate_prop_forge-<version>.zip, instalable en Blender (Preferencias > Add-ons > Instalar desde disco)."""
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "addon" / "pirate_prop_forge"
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIX = {".pyc", ".pyo"}


def build(out_dir=None):
    manifest = tomllib.loads((SRC / "blender_manifest.toml").read_text(encoding="utf-8"))
    out_dir = Path(out_dir or ROOT / "dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ("%s-%s.zip" % (manifest["id"], manifest["version"]))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SRC.rglob("*")):
            rel = path.relative_to(SRC)
            if path.is_dir() or set(rel.parts) & SKIP_DIRS or path.suffix in SKIP_SUFFIX:
                continue
            zf.write(path, rel.as_posix())  # los archivos van en la raiz del zip
    return target


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else None))
