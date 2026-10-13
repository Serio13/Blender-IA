import bpy


class PF_PT_main(bpy.types.Panel):
    bl_label = "Prop Forge"
    bl_idname = "PF_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Prop Forge"

    def draw(self, context):
        pf = context.scene.pf
        col = self.layout.column(align=True)
        col.prop(pf, "asset_name")
        col.prop(pf, "token_saver")
        self.layout.operator("pf.profile", icon="INFO")


class PF_PT_lods(bpy.types.Panel):
    bl_label = "LODs"
    bl_idname = "PF_PT_lods"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Prop Forge"
    bl_parent_id = "PF_PT_main"

    def draw(self, context):
        pf = context.scene.pf
        col = self.layout.column(align=True)
        col.prop(pf, "preset")
        col.prop(pf, "min_tris")
        col.prop(pf, "skip_below")
        col.prop(pf, "dissolve_deg")
        col.prop(pf, "smooth_deg")
        col.prop(pf, "keep_uv2")
        col.prop(pf, "spread")
        row = self.layout.row(align=True)
        row.operator("pf.lods", icon="MOD_DECIM")
        row.operator("pf.clean_lods", icon="TRASH", text="")


class PF_PT_export(bpy.types.Panel):
    bl_label = "Exportar a Unity"
    bl_idname = "PF_PT_export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Prop Forge"
    bl_parent_id = "PF_PT_main"

    def draw(self, context):
        pf = context.scene.pf
        col = self.layout.column(align=True)
        col.prop(pf, "out_dir")
        row = col.row(align=True)
        row.prop(pf, "export_fbx", toggle=True)
        row.prop(pf, "export_blend", toggle=True)
        col.prop(pf, "layout")
        col.prop(pf, "collider")
        col.prop(pf, "verify")
        self.layout.operator("pf.export", icon="EXPORT")


classes = (PF_PT_main, PF_PT_lods, PF_PT_export)
