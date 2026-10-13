"""Stable Fast 3D (Stability AI). Imagen -> malla GLB con UV y texturas PBR.

Modelo con acceso restringido en Hugging Face: aceptar la licencia en
https://huggingface.co/stabilityai/stable-fast-3d y configurar un token (HF_TOKEN).
Requiere el repositorio `stable-fast-3d` instalado en el entorno del worker (lo hace el instalador).
"""
from . import _common
from .base import Backend as _Base, JobCancelled


class Backend(_Base):
    name = "sf3d"
    output_format = "glb"

    def __init__(self):
        self.model = None
        self.rembg_session = {}

    def available(self):
        for mod in ("torch", "sf3d", "rembg", "PIL"):
            if not _common.has(mod):
                return False, "falta el modulo '%s' (ejecuta el instalador de IA)" % mod
        return True, ""

    def _load(self, progress):
        if self.model is not None:
            return
        import torch
        from sf3d.system import SF3D
        progress(0.05, "cargando modelo (la primera vez descarga ~1 GB)")
        device = _common.pick_device()
        self.device = device
        self.model = SF3D.from_pretrained("stabilityai/stable-fast-3d", config_name="config.yaml",
                                          weight_name="model.safetensors")
        self.model.to(device)
        self.model.eval()

    def generate(self, image_path, out_path, params, progress, cancelled):
        import torch
        from PIL import Image
        from sf3d.utils import resize_foreground
        self._load(progress)
        if cancelled():
            raise JobCancelled()
        progress(0.2, "preparando imagen")
        image = Image.open(image_path).convert("RGBA")
        if params.get("remove_bg", True):
            image = _common.remove_background(image, self.rembg_session)
        image = resize_foreground(image, float(params.get("foreground_ratio", 0.85)))
        if cancelled():
            raise JobCancelled()
        progress(0.45, "generando malla y texturas")
        res = int(params.get("texture_resolution", 1024))
        remesh = {"none": "none", "triangle": "triangle", "quad": "quad"}.get(params.get("remesh", "none"), "none")
        with torch.no_grad():
            if self.device == "cuda" and _common.supports_bf16():
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    mesh, _ = self.model.run_image(image, bake_resolution=res, remesh=remesh, vertex_count=-1)
            else:                                     # GTX 1080 Ti (Pascal): FP32
                mesh, _ = self.model.run_image(image, bake_resolution=res, remesh=remesh, vertex_count=-1)
        progress(0.95, "guardando")
        mesh.export(out_path, include_normals=True)
        _common.free_gpu()
        return {"has_uv": True, "has_texture": True}

    def unload(self):
        self.model = None
        _common.free_gpu()
