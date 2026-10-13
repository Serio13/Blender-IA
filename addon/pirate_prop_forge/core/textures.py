"""Extraccion de texturas empaquetadas a PNG y empaquetado Metallic+Smoothness para Unity URP."""
from pathlib import Path

import bpy
import numpy as np

# tipo canonico -> alias (en minusculas) del sufijo del nombre de la imagen
KIND_ALIASES = {
    "BaseMap": ("basecolor", "albedo", "color", "diffuse", "basemap"),
    "Normal": ("normal", "normalmap", "bump"),
    "Metallic": ("metallic", "metal", "metalness"),
    "Roughness": ("roughness", "rough"),
    "MetalSmooth": ("metalsmooth", "metalsmoothness", "metallicsmoothness", "metallicsmooth"),
    "Emission": ("emission", "emissive"),
    "Occlusion": ("ao", "occlusion"),
}
_ALIAS = {a: kind for kind, aliases in KIND_ALIASES.items() for a in aliases}

# nombres de salida; Metallic+Roughness se funden en MetallicSmoothness
OUT_SUFFIX = {
    "BaseMap": "BaseMap",
    "Normal": "Normal",
    "MetallicSmoothness": "MetallicSmoothness",
    "Emission": "Emission",
    "Occlusion": "Occlusion",
}
# propiedad del shader Universal Render Pipeline/Lit de Unity
URP_PROPERTY = {
    "BaseMap": "_BaseMap",
    "Normal": "_BumpMap",
    "MetallicSmoothness": "_MetallicGlossMap",
    "Emission": "_EmissionMap",
    "Occlusion": "_OcclusionMap",
}


def image_kind(name):
    token = name.rsplit("_", 1)[-1].lower().replace(".", "")
    return _ALIAS.get(token)


def collect_images(objs):
    """{tipo: imagen} a partir de los materiales de los objetos; ignora tipos no reconocidos."""
    found, unknown = {}, []
    seen_mats = set()
    for obj in objs:
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None or mat.name in seen_mats or mat.node_tree is None:
                continue
            seen_mats.add(mat.name)
            for node in mat.node_tree.nodes:
                if node.type != "TEX_IMAGE" or node.image is None:
                    continue
                kind = image_kind(node.image.name)
                if kind is None:
                    unknown.append(node.image.name)
                elif kind not in found:
                    found[kind] = node.image
    return found, unknown


def _read(img):
    w, h = img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    return arr.reshape(h, w, 4)


def _resize(arr, h, w):
    if arr.shape[0] == h and arr.shape[1] == w:
        return arr
    ys = (np.arange(h) * arr.shape[0] / h).astype(int)
    xs = (np.arange(w) * arr.shape[1] / w).astype(int)
    return arr[ys][:, xs]


def _save_array(arr, path, srgb):
    h, w = arr.shape[:2]
    img = bpy.data.images.new("_pf_out", w, h, alpha=True, float_buffer=False)
    try:
        img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
        img.alpha_mode = "CHANNEL_PACKED"
        img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


def _save_copy(src, path):
    img = src.copy()
    try:
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


def write_texture_set(images, out_dir, asset):
    """Escribe PNGs en out_dir. Devuelve (lista_de_archivos, avisos).

    Cada archivo: {"kind", "file", "size", "unity_property"}.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files, warnings = [], []

    def record(kind, path, size):
        files.append({"kind": kind, "file": path.name, "size": list(size),
                      "unity_property": URP_PROPERTY[kind]})

    images = dict(images)
    for kind, img in list(images.items()):
        if img.size[0] == 0 or img.size[1] == 0:
            warnings.append("imagen vacia o no encontrada, se omite: %s" % img.name)
            del images[kind]

    for kind in ("BaseMap", "Normal", "Emission", "Occlusion"):
        img = images.get(kind)
        if img is None:
            continue
        path = out_dir / ("%s_%s.png" % (asset, OUT_SUFFIX[kind]))
        _save_copy(img, path)
        record(kind, path, img.size)

    path = out_dir / ("%s_%s.png" % (asset, OUT_SUFFIX["MetallicSmoothness"]))
    if "MetalSmooth" in images:
        _save_copy(images["MetalSmooth"], path)
        record("MetallicSmoothness", path, images["MetalSmooth"].size)
    elif "Metallic" in images or "Roughness" in images:
        metal, rough = images.get("Metallic"), images.get("Roughness")
        ref = metal or rough
        h, w = ref.size[1], ref.size[0]
        if metal is not None and rough is not None and tuple(metal.size) != tuple(rough.size):
            h, w = max(metal.size[1], rough.size[1]), max(metal.size[0], rough.size[0])
            warnings.append("Metallic y Roughness con distinto tamano: se igualan a %dx%d" % (w, h))
        m = _resize(_read(metal), h, w)[..., 0] if metal is not None else np.zeros((h, w), np.float32)
        smooth = (1.0 - _resize(_read(rough), h, w)[..., 0]) if rough is not None else np.full((h, w), 0.5, np.float32)
        out = np.stack([m, m, m, smooth], axis=-1)
        _save_array(out, path, srgb=False)
        record("MetallicSmoothness", path, (w, h))
        if metal is None:
            warnings.append("sin textura Metallic: se asume metalico 0")
        if rough is None:
            warnings.append("sin textura Roughness: se asume smoothness 0.5")
    return files, warnings


def render_uv_name(objs):
    """Nombre de la capa UV que fuerza el material con un nodo UV Map (tambien tras un nodo Mapping), o None."""
    seen = set()
    for obj in objs:
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None or mat.name in seen or mat.node_tree is None:
                continue
            seen.add(mat.name)
            for node in mat.node_tree.nodes:
                if node.type != "TEX_IMAGE":
                    continue
                socket = node.inputs.get("Vector")
                for _ in range(4):
                    if socket is None or not socket.is_linked:
                        break
                    src = socket.links[0].from_node
                    if src.type == "UVMAP":
                        if src.uv_map:
                            return src.uv_map
                        break
                    socket = src.inputs.get("Vector")
    return None
