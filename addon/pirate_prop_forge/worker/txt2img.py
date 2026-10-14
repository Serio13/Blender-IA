"""Texto -> imagen de referencia, en local (Stable Diffusion 1.5). Despues la imagen pasa a SF3D/TripoSR.

La imagen se guarda en disco y el plugin la muestra, para que veas que ha entendido el pedido antes de gastar
tiempo en la malla. Las funciones pesadas se importan dentro de generate() (en el hilo principal del worker).
"""
import os
import struct
import zlib

from backends._common import free_gpu, has
from backends.base import JobCancelled

MODEL_ID = os.environ.get("PF_TXT2IMG_MODEL", "stable-diffusion-v1-5/stable-diffusion-v1-5")
TEMPLATE = ("{p}, single object, centered, isolated on a plain white background, three-quarter view, "
            "stylized game asset, clean simple shapes, soft even lighting, highly detailed")
NEGATIVE = ("text, watermark, logo, multiple objects, cropped, out of frame, blurry, low quality, person, hands, "
            "floor, ground shadow, busy background, frame, border")


def _write_png(path, size, rgb):
    row = b"\x00" + bytes(rgb) * size
    raw = row * size

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Fake:
    name = "fake"

    def available(self):
        return True, ""

    def generate(self, prompt, seed, out_path, progress, cancelled):
        for i in range(3):
            if cancelled():
                raise JobCancelled()
            progress((i + 1) / 3, "paso %d/3" % (i + 1))
        _write_png(out_path, 32, (200, 170, 120))
        return {"prompt": TEMPLATE.format(p=prompt), "seed": seed}


class SD15:
    name = "sd15"

    def available(self):
        for mod in ("torch", "diffusers", "transformers", "PIL"):
            if not has(mod):
                return False, "falta '%s' (vuelve a ejecutar instalar_ia.bat)" % mod
        return True, ""

    def generate(self, prompt, seed, out_path, progress, cancelled):
        import numpy as np
        import torch
        from diffusers import DPMSolverMultistepScheduler, StableDiffusionPipeline
        progress(0.02, "cargando Stable Diffusion (la primera vez descarga ~4 GB)")
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        kw = dict(torch_dtype=dtype, safety_checker=None, requires_safety_checker=False, use_safetensors=True)
        try:
            pipe = StableDiffusionPipeline.from_pretrained(MODEL_ID, variant="fp16" if dtype == torch.float16 else None, **kw)
        except Exception:                                   # noqa: BLE001  (repo sin variante fp16)
            pipe = StableDiffusionPipeline.from_pretrained(MODEL_ID, **kw)
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True)
        pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")
        pipe.set_progress_bar_config(disable=True)
        steps = 28
        if seed is None or int(seed) <= 0:
            seed = int.from_bytes(os.urandom(3), "big")
        gen = torch.Generator(device=pipe.device.type).manual_seed(int(seed))

        def on_step(pipeline, i, t, kwargs):
            if cancelled():
                raise JobCancelled()
            progress(0.1 + 0.85 * (i + 1) / steps, "dibujando %d/%d" % (i + 1, steps))
            return kwargs
        full = TEMPLATE.format(p=prompt)
        try:
            image = pipe(full, negative_prompt=NEGATIVE, num_inference_steps=steps, guidance_scale=7.5, width=512, height=512,
                         generator=gen, callback_on_step_end=on_step).images[0]
        finally:
            del pipe
            free_gpu()                                      # deja la VRAM libre para SF3D
        if np.asarray(image).max() < 8:
            raise RuntimeError("la imagen salio negra (problema numerico de la GPU en fp16)")
        image.save(out_path)
        return {"prompt": full, "seed": int(seed)}


REGISTRY = {"fake": Fake, "sd15": SD15}


def get(name):
    if name not in REGISTRY:
        raise KeyError("modelo de imagen desconocido: %s" % name)
    return REGISTRY[name]()


def info():
    """Para el evento `ready`: disponibilidad de cada modelo de imagen."""
    out = {}
    for name, cls in REGISTRY.items():
        ok, why = cls().available()
        out[name] = {"available": ok, "reason": why}
    return out
