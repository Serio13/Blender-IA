"""Registro de generadores (arquetipos)."""
REGISTRY = {}


def register(cls):
    REGISTRY[cls.archetype] = cls
    return cls


def get(archetype):
    from . import barrel  # noqa: F401  (registra los generadores al importar)
    if archetype not in REGISTRY:
        raise KeyError(archetype)
    return REGISTRY[archetype]
