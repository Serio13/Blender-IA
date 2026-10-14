bl_info = {
    "name": "Pirate Prop Forge",
    "author": "Serio13",
    "version": (0, 2, 7),
    "blender": (4, 2, 0),
    "location": "Vista 3D > Barra lateral (N) > Prop Forge",
    "description": "IA local imagen a malla, normalizacion, PBR, LODs y exportacion para Unity",
    "category": "Import-Export",
}

from . import ui


def register():
    ui.register()


def unregister():
    ui.unregister()
