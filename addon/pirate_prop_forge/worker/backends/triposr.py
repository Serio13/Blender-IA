"""TripoSR (Stability AI + Tripo, licencia MIT). Imagen -> malla con color por vertice (sin UV)."""
from . import _common
from .base import Backend as _Base, JobCancelled


class Backend(_Base):
    name = "triposr"
    output_format = "glb"

    def __init__(self):
        self.model = None
        self.rembg_session = {}

    def available(self):
        for mod in ("torch", "tsr", "rembg", "PIL", "numpy", "trimesh"):
            if not _common.has(mod):
                return False, "falta el modulo '%s' (instala TripoSR en el entorno del worker)" % mod
        return True, ""

    def _load(self, progress):
        if self.model is not None:
            return
        from tsr.system import TSR
        progress(0.05, "cargando modelo")
        self.device = _common.pick_device()
        self.model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
        self.model.renderer.set_chunk_size(8192)
        self.model.to(self.device)

    def generate(self, image_path, out_path, params, progress, cancelled):
        import numpy as np
        import torch
        from PIL import Image
        from tsr.utils import resize_foreground
        self._load(progress)
        progress(0.2, "preparando imagen")
        image = Image.open(image_path).convert("RGBA")
        if params.get("remove_bg", True):
            image = _common.remove_background(image, self.rembg_session)
        image = resize_foreground(image, float(params.get("foreground_ratio", 0.85)))
        arr = np.array(image).astype(np.float32) / 255.0
        arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5
        image = Image.fromarray((arr * 255.0).astype(np.uint8))
        if cancelled():
            raise JobCancelled()
        progress(0.45, "generando")
        with torch.no_grad():
            codes = self.model([image], device=self.device)
        if cancelled():
            raise JobCancelled()
        progress(0.8, "extrayendo malla")
        mesh = self.model.extract_mesh(codes, True, resolution=int(params.get("mc_resolution", 256)))[0]
        mesh.export(out_path)
        _common.free_gpu()
        return {"has_uv": False, "has_texture": False, "vertex_colors": True}

    def unload(self):
        self.model = None
        _common.free_gpu()
