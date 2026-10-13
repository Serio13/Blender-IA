bl_info = {
    "name": "Pirate Prop Forge",
    "author": "Serio13",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "Vista 3D > Barra lateral (N) > Prop Forge",
    "description": "LODs y paquete de exportacion para Unity de props estilizados",
    "category": "Import-Export",
}

from . import ui


def register():
    ui.register()


def unregister():
    ui.unregister()
