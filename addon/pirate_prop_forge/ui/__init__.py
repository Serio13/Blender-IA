import bpy

from . import operators, panel, prefs, props

_classes = prefs.classes + props.classes + operators.classes + panel.classes


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pf = bpy.props.PointerProperty(type=props.PF_Settings)


def unregister():
    panel.free_previews()
    del bpy.types.Scene.pf
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
