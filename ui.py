"""侧栏面板 + 菜单项注册由 __init__ 调用。"""
from __future__ import annotations

import bpy

from .operators import PROP_AXIS, PROP_ORIGIN, PROP_ORIGIN_SRC, PROP_PATH


class SND_PT_panel(bpy.types.Panel):
    bl_label = "X-Plane SND"
    bl_idname = "SND_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "X-Plane"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        path = scene.get(PROP_PATH)
        col = layout.column(align=True)
        if path:
            col.label(text=bpy.path.basename(path), icon="SOUND")
            origin = scene.get(PROP_ORIGIN)
            if origin:
                col.label(text="原点 %s" % scene.get(PROP_ORIGIN_SRC, "?"))
                col.label(text="(%.3f, %.3f, %.3f) m" % tuple(origin))
            col.label(text="轴向 %s" % scene.get(PROP_AXIS, "XP2B"))
        else:
            col.label(text="未导入 .snd", icon="INFO")

        n = len([o for o in scene.objects if "snd_uid" in o])
        unsaved = len([o for o in scene.objects if "snd_uid" in o and int(o.get("snd_uid", -1)) < 0])
        col.label(text="%d 个 attachment%s" % (n, ("，%d 个新增" % unsaved) if unsaved else ""))

        layout.separator()
        layout.operator("export_scene.xplane_snd", text="写回 .snd", icon="FILE_TICK")
        row = layout.row(align=True)
        row.operator("sound.xplane_snd_solo", text="Solo 选中", icon="SOLO_ON")
        row.operator("sound.xplane_snd_mute_all", text="全部静音", icon="MUTE_IPO_OFF")


CLASSES = (SND_PT_panel,)
