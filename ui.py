"""侧栏面板：文件信息 + 事件（N:1）列表。菜单项注册由 __init__ 调用。"""
from __future__ import annotations

import bpy

from .operators import PROP_AXIS, PROP_ORIGIN, PROP_ORIGIN_SRC, PROP_PATH


class SND_UL_events(bpy.types.UIList):
    """一个 EVENT_NAME 一行：左边事件路径，右边这个事件有几个 Speaker。"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.event, icon="SOUND")
        row.label(text="%d" % item.count)


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

        # ---------------- 事件（.snd 里 EVENT_NAME : VEH_XYZ 是 1:N）
        box = layout.box()
        head = box.row(align=True)
        head.label(text="事件 %d 个" % len(scene.snd_events), icon="PRESET")
        head.operator("snd.refresh_events", text="", icon="FILE_REFRESH")
        if len(scene.snd_events):
            box.template_list("SND_UL_events", "", scene, "snd_events",
                              scene, "snd_events_index", rows=6)
            row = box.row(align=True)
            row.operator("snd.select_event", text="选中", icon="RESTRICT_SELECT_OFF")
            row.operator("snd.isolate_event", text="隔离", icon="VIEW3D")
            row = box.row(align=True)
            row.prop(scene, "snd_event_new", text="")
            row.operator("snd.rename_event", text="整组改名", icon="SORTALPHA")
        else:
            box.label(text="（导入后自动列出）")

        # ---------------- sound space（听感分区，只读参考）
        space_objs = [o for o in scene.objects if "snd_space_index" in o]
        if space_objs:
            shelf = layout.box()
            head = shelf.row(align=True)
            head.label(text="听感分区 %d 个" % len({int(o["snd_space_index"]) for o in space_objs}),
                       icon="MOD_LATTICE")
            head.operator("snd.toggle_spaces", text="", icon="HIDE_ON")
            for idx in sorted({int(o["snd_space_index"]) for o in space_objs}):
                group = [o for o in space_objs if int(o["snd_space_index"]) == idx]
                probe = next((o for o in group if o.get("snd_space_role") == "boundary"), group[0])
                area = probe.get("snd_space_area") or ("space %d" % idx)
                kind = probe.get("snd_space_kind", "?")
                sound = "inside_ratio[%d]" % int(probe["snd_sound_index"]) \
                    if "snd_sound_index" in probe else "index ?"
                blend = probe.get("snd_blend_depth")
                row = shelf.row()
                row.label(text="%s · %s · %s%s" % (
                    area, kind, sound,
                    (" · blend %.2f m" % float(blend)) if blend else ""), icon="DOT")
                row.label(text="%d" % int(len(group)))
            shelf.label(text="拖/缩放外框 = 改该体积；导出时写回", icon="INFO")
            shelf.label(text="改 snd_blend_depth 属性 = 改 BLEND_DEPTH")


CLASSES = (SND_UL_events, SND_PT_panel)
