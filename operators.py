"""导入 / 导出 / 试听操作符。只用 Blender 自带 API，不依赖 XPlane2Blender。"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatVectorProperty, IntProperty, StringProperty)
from bpy.types import OperatorFileListElement
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import acftool
from .document import Document, read_file, write_file

# 会话内的文档缓存：scene.name -> Document
_DOCS: dict[str, Document] = {}
PROP_PATH = "xplane_snd_path"
PROP_SRC_B64 = "xplane_snd_source_b64"
PROP_ORIGIN = "xplane_snd_origin"
PROP_ORIGIN_SRC = "xplane_snd_origin_source"
PROP_AXIS = "xplane_snd_axis"
PROP_OWNERS = "xplane_snd_owners"      # {"uid": "对象名"}，用来区分"原对象"和 Shift+D 副本


# ---------------------------------------------------------------- helpers
def get_doc(scene):
    """取当前场景对应的 Document：优先内存缓存，其次从场景里存的原文件重建。"""
    doc = _DOCS.get(scene.name)
    if doc is not None:
        return doc
    b64 = scene.get(PROP_SRC_B64)
    if not b64:
        return None
    text = base64.b64decode(b64).decode("utf-8", "surrogateescape")
    doc = Document(text)
    _DOCS[scene.name] = doc
    return doc


def store_doc(scene, doc: Document, path: str, origin, origin_src):
    _DOCS[scene.name] = doc
    scene[PROP_SRC_B64] = base64.b64encode(doc.text_in.encode("utf-8", "surrogateescape")).decode("ascii")
    scene[PROP_PATH] = str(path)
    scene[PROP_ORIGIN] = [float(v) for v in origin]
    scene[PROP_ORIGIN_SRC] = str(origin_src)


def snd_objects(scene):
    return [o for o in scene.objects if "snd_uid" in o]


def _xyz_prop(obj):
    v = obj.get("snd_xyz")
    return tuple(float(x) for x in v) if v else None


# ---------------------------------------------------------------- events（N:1 关系）
class SND_EventItem(bpy.types.PropertyGroup):
    event: StringProperty(default="")
    count: IntProperty(default=0)


def register_props():
    bpy.types.Scene.snd_events = CollectionProperty(type=SND_EventItem)
    bpy.types.Scene.snd_events_index = IntProperty(default=0)
    bpy.types.Scene.snd_event_new = StringProperty(name="新事件名", default="")


def unregister_props():
    for attr in ("snd_events", "snd_events_index", "snd_event_new"):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)

def event_groups(scene):
    """scene 里的对象按 snd_event 分组：{事件名: [对象...]}（保持导入顺序）。"""
    groups = {}
    for obj in snd_objects(scene):
        name = obj.get("snd_event")
        if not name:
            continue
        groups.setdefault(str(name), []).append(obj)
    return groups


def refresh_events(scene):
    """把场景里的事件列表刷进 Scene.snd_events（面板用）。"""
    groups = event_groups(scene)
    items = scene.snd_events
    items.clear()
    for name in sorted(groups):
        item = items.add()
        item.name = name          # 注意：CollectionProperty 的 name 会被去重，所以再存一份
        item.event = name
        item.count = len(groups[name])
    scene.snd_events_index = min(scene.snd_events_index, max(0, len(items) - 1))
    return len(items)


class SND_OT_refresh_events(bpy.types.Operator):
    """刷新事件列表"""
    bl_idname = "snd.refresh_events"
    bl_label = "刷新事件列表"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = refresh_events(context.scene)
        self.report({"INFO"}, "共 %d 个事件" % n)
        return {"FINISHED"}


def _selected_event(scene):
    idx = scene.snd_events_index
    if 0 <= idx < len(scene.snd_events):
        return scene.snd_events[idx].event
    return None


class SND_OT_select_event(bpy.types.Operator):
    """选中这个事件的全部 Speaker"""
    bl_idname = "snd.select_event"
    bl_label = "选中该事件"
    bl_options = {"REGISTER", "UNDO"}

    event: StringProperty(default="")

    def execute(self, context):
        name = self.event or _selected_event(context.scene)
        objs = event_groups(context.scene).get(name, [])
        if not objs:
            self.report({"WARNING"}, "没有对象属于事件 %s" % name)
            return {"CANCELLED"}
        for obj in context.scene.objects:
            obj.select_set(False)
        for obj in objs:
            obj.select_set(True)
        if context.view_layer.objects.active is None or context.view_layer.objects.active not in objs:
            context.view_layer.objects.active = objs[0]
        self.report({"INFO"}, "选中 %d 个对象（%s）" % (len(objs), name))
        return {"FINISHED"}


class SND_OT_isolate_event(bpy.types.Operator):
    """只显示这个事件的 Speaker（局部视图开/关）"""
    bl_idname = "snd.isolate_event"
    bl_label = "隔离该事件"
    bl_options = {"REGISTER", "UNDO"}

    event: StringProperty(default="")

    def execute(self, context):
        if context.space_data is None or context.space_data.type != "VIEW_3D":
            self.report({"WARNING"}, "请在 3D 视口里用")
            return {"CANCELLED"}
        bpy.ops.object.select_all(action="DESELECT")
        res = SND_OT_select_event.execute(self, context)
        if "FINISHED" not in res:
            return res
        bpy.ops.view3d.localview()
        return {"FINISHED"}


class SND_OT_rename_event(bpy.types.Operator):
    """把这个事件下所有 Speaker 的 EVENT_NAME 改成新值（只改 Blender 里的数据，写回时生效）"""
    bl_idname = "snd.rename_event"
    bl_label = "整组改名"
    bl_options = {"REGISTER", "UNDO"}

    event: StringProperty(default="")
    new_name: StringProperty(default="")

    def execute(self, context):
        old = self.event or _selected_event(context.scene)
        # 面板上的输入框是 Scene.snd_event_new，操作符自己的 new_name 只在脚本调用时用
        # 注意：snd_event_new 是注册过的 RNA 属性，scene.get() 读不到，必须 getattr
        new = (self.new_name or getattr(context.scene, "snd_event_new", "") or "").strip()
        if not old or not new:
            self.report({"WARNING"}, "事件名不能为空")
            return {"CANCELLED"}
        objs = event_groups(context.scene).get(old, [])
        for obj in objs:
            obj["snd_event"] = new
        scene = context.scene
        if scene.get(PROP_PATH):
            coll = bpy.data.collections.get("SND " + os.path.basename(scene[PROP_PATH]) + " / "
                                            + old.strip("/").replace("/", " / "))
            if coll is not None:
                coll["snd_event"] = new
        refresh_events(scene)
        self.report({"INFO"}, "%d 个对象改成 %s" % (len(objs), new))
        return {"FINISHED"}


# ---------------------------------------------------------------- import
class IMPORT_OT_xplane_snd(bpy.types.Operator, ImportHelper):
    """导入 X-Plane .snd（每个 attachment 一个 Speaker）"""
    bl_idname = "import_scene.xplane_snd"
    bl_label = "X-Plane SND (.snd)"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".snd"
    filter_glob: StringProperty(default="*.snd", options={"HIDDEN"})
    # 拖拽导入时 Blender 会填这个集合（ImportHelper 本身没有 files，得自己声明）
    files: CollectionProperty(type=OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    group_events: BoolProperty(
        name="按事件分组",
        description="同一个 EVENT_NAME 的 attachment 归到一个 Collection 里（.snd 里 event:attachment 是 1:N）",
        default=True,
    )
    make_speakers: BoolProperty(
        name="用 Speaker 对象",
        description="关闭则用 Empty（Speaker 可以试听、能显示锥体朝向）",
        default=True,
    )
    axis_mode: EnumProperty(
        name="轴向",
        description="Blender 坐标怎么摆。XP2B 与 io_scene_xplane_obj 导入的网格对齐",
        items=(
            ("XP2B", "对齐导入网格 (XP2B)", "(x, y, z) -> (x, -z, y)，与 io_scene_xplane_obj 一致"),
            ("RAW", "原始飞机坐标", "飞机坐标直接当 Blender 坐标（X右/Y上/Z后）"),
        ),
        default="XP2B",
    )

    def invoke(self, context, event):
        # 从视口/文件浏览器拖进来时，Blender 会带上 files 列表：直接导入，不弹对话框。
        # 走 File > Import 菜单时 files 是空的，仍然正常弹文件浏览器。
        if getattr(self, "files", None):
            return self.execute(context)
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        scene = context.scene
        path = self.filepath
        try:
            doc = read_file(path)
        except OSError as exc:
            self.report({"ERROR"}, "读取失败: %s" % exc)
            return {"CANCELLED"}

        if len(getattr(self, "files", []) or []) > 1:
            self.report({"WARNING"}, "一次只导入一个 .snd（拖入多个时只处理第一个）")

        origin, origin_src, warn = acftool.resolve_origin(doc, path)
        store_doc(scene, doc, path, origin, origin_src)
        axis = self.axis_mode
        scene[PROP_AXIS] = axis

        coll_name = "SND " + os.path.basename(path)
        coll = bpy.data.collections.get(coll_name) or bpy.data.collections.new(coll_name)
        if coll.name not in scene.collection.children:
            scene.collection.children.link(coll)

        owners = {}
        ev_colls = {}

        def event_coll(event_name):
            """一个 EVENT_NAME 一个 collection，挂在 "SND <file>" 下面。"""
            key = event_name.strip("/").replace("/", " / ") or "unnamed"
            got = ev_colls.get(key) or bpy.data.collections.get(coll_name + " / " + key)
            if got is None:
                got = bpy.data.collections.new(coll_name + " / " + key)
                got["snd_event"] = event_name
                coll.children.link(got)
            ev_colls[key] = got
            return got

        made = 0
        for att in doc.attachments:
            if att.name is None:
                continue
            base = "SND_%03d_%s" % (att.index, att.name.strip("/").replace("/", "_"))
            if self.make_speakers:
                data = bpy.data.speakers.new(base)
                data.muted = True
                obj = bpy.data.objects.new(base, data)
            else:
                obj = bpy.data.objects.new(base, None)
            (event_coll(att.name) if self.group_events else coll).objects.link(obj)

            # 位置：作者坐标 = VEH_XYZ + 原点，再按轴向模式转到 Blender 坐标
            xp_pos = att.xyz if att.xyz is not None else (0.0, 0.0, 0.0)
            world = (xp_pos[0] + origin[0], xp_pos[1] + origin[1], xp_pos[2] + origin[2])
            obj.location = acftool.to_blender(world, axis)

            obj["snd_uid"] = int(att.index)
            owners[str(int(att.index))] = obj.name
            obj["snd_kind"] = att.kind
            obj["snd_event"] = att.name
            obj["snd_xyz"] = [float(v) for v in (att.xyz or (0.0, 0.0, 0.0))]
            obj["snd_has_xyz"] = att.xyz is not None
            obj["snd_line"] = int(att.begin_line)
            if att.part is not None:
                obj["snd_part"] = "%s %d" % (att.part[0], att.part[1])
            if att.dref_idx is not None:
                obj["snd_dref_idx"] = int(att.dref_idx)
            if att.the is not None:
                obj["snd_the"] = float(att.the)
            if att.psi is not None:
                obj["snd_psi"] = float(att.psi)
            if att.phi is not None:
                obj["snd_phi"] = float(att.phi)
            if att.flags:
                obj["snd_flags"] = ",".join(att.flags)
            if att.conds:
                obj["snd_conds"] = "\n".join("%s %s" % (k, v) for k, v in att.conds)
            made += 1

        scene[PROP_OWNERS] = json.dumps(owners)
        refresh_events(scene)

        for w in doc.warnings:
            self.report({"WARNING"}, w)
        if warn:
            self.report({"WARNING"}, warn)

        self.report(
            {"INFO"},
            "导入 %d 个 attachment（%d 个 space）· 原点 %s = (%.3f, %.3f, %.3f) · 轴向 %s"
            % (made, len(doc.spaces), origin_src, origin[0], origin[1], origin[2], axis),
        )
        return {"FINISHED"}


# ---------------------------------------------------------------- export
class EXPORT_OT_xplane_snd(bpy.types.Operator, ExportHelper):
    """把改动 patch 回 .snd（没动过的行原样输出）"""
    bl_idname = "export_scene.xplane_snd"
    bl_label = "X-Plane SND (.snd)"
    bl_options = {"REGISTER"}

    filename_ext = ".snd"
    filter_glob: StringProperty(default="*.snd", options={"HIDDEN"})

    def invoke(self, context, event):
        scene = context.scene
        if not self.filepath and scene.get(PROP_PATH):
            self.filepath = scene.get(PROP_PATH)
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        scene = context.scene
        doc = get_doc(scene)
        if doc is None:
            self.report({"ERROR"}, "场景里没有已导入的 .snd")
            return {"CANCELLED"}

        origin = tuple(scene.get(PROP_ORIGIN, (0.0, 0.0, 0.0)))
        axis = scene.get(PROP_AXIS, "XP2B")

        # uid 归谁：同一个 uid 可能有多个对象（用户 Shift+D 复制出来的副本）。
        # 导入时把 uid -> 对象名 记进场景，导出时按名字认领**原对象**，
        # 名字对不上的（副本 / 改名后的新对象）一律当新增处理。
        # 没有记录（老场景）或名字被改过时，退化成"第一个遇到的对象算原对象"。
        try:
            owners = json.loads(scene.get(PROP_OWNERS, "{}") or "{}")
        except ValueError:
            owners = {}
        by_uid = {}
        extras = []
        dup_uid = 0
        for obj in snd_objects(scene):
            uid = int(obj.get("snd_uid", -1))
            if not (0 <= uid < len(doc.attachments)):
                extras.append(obj)
                continue
            want = owners.get(str(uid))
            if want is None or obj.name == want:
                if uid in by_uid:
                    dup_uid += 1
                    extras.append(obj)
                else:
                    by_uid[uid] = obj
            else:
                dup_uid += 1
                extras.append(obj)

        patched, changed_fields = 0, []
        for att in doc.attachments:
            obj = by_uid.get(att.index)
            if obj is None:
                continue
            # 只有原本就有 VEH_XYZ 的才回写坐标（VEH_PART 的没有坐标可写）
            xyz = None
            if att.xyz is not None and obj.get("snd_has_xyz", True):
                world = acftool.from_blender(tuple(obj.location), axis)
                xyz = (world[0] - origin[0], world[1] - origin[1], world[2] - origin[2])
            changed = doc.patch_attachment(
                att, name=obj.get("snd_event"), xyz=xyz,
                the=obj.get("snd_the"), psi=obj.get("snd_psi"), phi=obj.get("snd_phi"),
            )
            if changed:
                patched += 1
                changed_fields.append((att.name, changed))

        # 新增的 Speaker（没有对应 attachment，或 uid 与别人撞车）追加到文件末尾
        added = 0
        for obj in extras:
            name = obj.get("snd_event")
            if not name:
                continue
            kind = obj.get("snd_kind", "event")
            loc = obj.location
            conds = []
            for line in str(obj.get("snd_conds", "")).splitlines():
                line = line.strip()
                if not line:
                    continue
                head, _, rest = line.partition(" ")
                conds.append((head, rest.strip()))
            flags = [f.strip() for f in str(obj.get("snd_flags", "")).split(",") if f.strip()]
            part = None
            if obj.get("snd_part"):
                bits = str(obj.get("snd_part")).split()
                if len(bits) >= 2:
                    part = (bits[0], int(bits[1]))
            world = acftool.from_blender(tuple(loc), axis)
            doc.append_attachment(
                kind=kind, name=name,
                xyz=(world[0] - origin[0], world[1] - origin[1], world[2] - origin[2]),
                remark=obj.name,
                the=obj.get("snd_the"), psi=obj.get("snd_psi"), phi=obj.get("snd_phi"),
                part=part, dref_idx=obj.get("snd_dref_idx"), flags=flags, conds=conds,
            )
            uid = int(doc.attachments[-1].index)
            obj["snd_uid"] = uid
            owners[str(uid)] = obj.name
            added += 1

        try:
            write_file(self.filepath, doc)
        except OSError as exc:
            self.report({"ERROR"}, "写入失败: %s" % exc)
            return {"CANCELLED"}

        scene[PROP_PATH] = self.filepath
        scene[PROP_OWNERS] = json.dumps(owners)
        refresh_events(scene)
        if dup_uid:
            self.report({"WARNING"},
                        "有 %d 个对象与已有 attachment 共用 snd_uid（多半是 Shift+D 复制出来的），"
                        "已按新增处理" % dup_uid)

        self.report(
            {"INFO"},
            "已写出 %s：改了 %d 个 attachment%s%s"
            % (os.path.basename(self.filepath), patched,
               ("，新增 %d 个" % added) if added else "",
               (" · " + "; ".join("%s:%s" % (n, "/".join(f)) for n, f in changed_fields[:4])) if changed_fields else ""),
        )
        return {"FINISHED"}


# ---------------------------------------------------------------- 试听辅助
class SND_OT_solo(bpy.types.Operator):
    """只让选中的 Speaker 发声（其余全部静音）"""
    bl_idname = "sound.xplane_snd_solo"
    bl_label = "Solo 选中"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sel = {o.name for o in context.selected_objects if o.type == "SPEAKER"}
        for o in context.scene.objects:
            if o.type == "SPEAKER" and "snd_uid" in o:
                o.data.muted = o.name not in sel
        self.report({"INFO"}, "已 solo %d 个 Speaker" % len(sel))
        return {"FINISHED"}


class SND_OT_mute_all(bpy.types.Operator):
    """全部静音（清场，避免 400 个 one-shot 一起响）"""
    bl_idname = "sound.xplane_snd_mute_all"
    bl_label = "全部静音"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = 0
        for o in context.scene.objects:
            if o.type == "SPEAKER" and "snd_uid" in o:
                o.data.muted = True
                n += 1
        self.report({"INFO"}, "已静音 %d 个 Speaker" % n)
        return {"FINISHED"}


CLASSES = (
    SND_EventItem,
    SND_OT_refresh_events,
    SND_OT_select_event,
    SND_OT_isolate_event,
    SND_OT_rename_event,IMPORT_OT_xplane_snd, EXPORT_OT_xplane_snd, SND_OT_solo, SND_OT_mute_all)
