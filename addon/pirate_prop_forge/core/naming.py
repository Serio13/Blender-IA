import re

BAKED_SUFFIX = "_BAKED"
PART_LABELS = ("base", "tapa", "malla")
_DUP_RE = re.compile(r"\.\d{3}$")


def strip_dup(name):
    """'Foo_BAKED.001' -> 'Foo_BAKED'."""
    return _DUP_RE.sub("", name)


def is_baked(name):
    return strip_dup(name).endswith(BAKED_SUFFIX)


def strip_baked(name):
    name = strip_dup(name)
    if name.endswith(BAKED_SUFFIX):
        name = name[: -len(BAKED_SUFFIX)]
    return name


def split_part(stem, labels=PART_LABELS):
    """'Cofre_V2_tapa' -> ('Cofre_V2', 'tapa'); sin etiqueta conocida -> (stem, '')."""
    for label in labels:
        suffix = "_" + label
        if stem.endswith(suffix) and len(stem) > len(suffix):
            return stem[: -len(suffix)], label
    return stem, ""


def classify(obj, labels=PART_LABELS):
    """Devuelve (nombre_de_asset, etiqueta_de_pieza) para un objeto malla."""
    stem = strip_baked(obj.name)
    parent = obj.parent
    if parent is not None and parent.type == "EMPTY":
        asset = strip_baked(parent.name)
        if stem == asset:
            return asset, ""
        if stem.startswith(asset + "_"):
            return asset, stem[len(asset) + 1:]
        return asset, stem
    return split_part(stem, labels)


def safe(name):
    """Nombre seguro para archivos y nodos FBX."""
    return re.sub(r"[^A-Za-z0-9_\-]", "_", name)


def family(asset_name):
    """'Cofre_comun_V2' -> 'Cofre' (primer token), para agrupar en el perfil."""
    return asset_name.split("_", 1)[0]
