"""导入 / 导出 / 试听操作符。只用 Blender 自带 API，不依赖 XPlane2Blender。"""
from __future__ import annotations

import base64
import os
from pathlib import Path

import bpy
from bpy.props import BoolProperty, FloatVectorProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import acftool
from .document import Document, read_file, write_file

# 会话内的文档缓存：scene.name -> Document
_DOCS: dict[str, Document] = {}
PROP_PATH = "xplane_snd_path"
PROP_SRC_B64 = "xplane_snd_source_b64"
PROP_ORIGIN = "xplane_snd_origin"
PROP_ORIGIN_SRC = "xplane_snd_origin_source"


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


# ---------------------------------------------------------------- import
class IMPORT_OT_xplane_snd(bpy.types.Operator, ImportHelper):
    """导入 X-Plane .snd（每个 attachment 一个 Speaker）"""
    bl_idname = "import_scene.xplane_snd"
    bl_label = "X-Plane SND (.snd)"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".snd"
    filter_glob: StringProperty(default="*.snd", options={"HIDDEN"})
    make_speakers: BoolProperty(
        name="用 Speaker 对象",
        description="关闭则用 Empty（Speaker 可以试听、能显示锥体朝向）",
        default=True,
    )

    def execute(self, context):
        scene = context.scene
        path = self.filepath
        try:
            doc = read_file(path)
        except OSError as exc:
            self.report({"ERROR"}, "读取失败: %s" % exc)
            return {"CANCELLED"}

        origin, origin_src, warn = acftool.resolve_origin(doc, path)
        store_doc(scene, doc, path, origin, origin_src)

        coll_name = "SND " + os.path.basename(path)
        coll = bpy.data.collections.get(coll_name) or bpy.data.collections.new(coll_name)
        if coll.name not in scene.collection.children:
            scene.collection.children.link(coll)

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
            coll.objects.link(obj)

            # 位置：作者坐标 = VEH_XYZ + 原点；没有 VEH_XYZ 的（VEH_PART）放在原点
            if att.xyz is not None:
                obj.location = (att.xyz[0] + origin[0], att.xyz[1] + origin[1], att.xyz[2] + origin[2])
            else:
                obj.location = tuple(origin)

            obj["snd_uid"] = int(att.index)
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

        for w in doc.warnings:
            self.report({"WARNING"}, w)
        if warn:
            self.report({"WARNING"}, warn)

        self.report(
            {"INFO"},
            "导入 %d 个 attachment（%d 个 space）· 原点 %s = (%.3f, %.3f, %.3f)"
            % (made, len(doc.spaces), origin_src, origin[0], origin[1], origin[2]),
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
        by_uid = {}
        for obj in snd_objects(scene):
            by_uid[int(obj.get("snd_uid", -1))] = obj

        patched, changed_fields = 0, []
        for att in doc.attachments:
            obj = by_uid.get(att.index)
            if obj is None:
                continue
            # 只有原本就有 VEH_XYZ 的才回写坐标（VEH_PART 的没有坐标可写）
            xyz = None
            if att.xyz is not None and obj.get("snd_has_xyz", True):
                loc = obj.location
                xyz = (loc[0] - origin[0], loc[1] - origin[1], loc[2] - origin[2])
            changed = doc.patch_attachment(
                att, xyz=xyz,
                the=obj.get("snd_the"), psi=obj.get("snd_psi"), phi=obj.get("snd_phi"),
            )
            if changed:
                patched += 1
                changed_fields.append((att.name, changed))

        # 新增的 Speaker（没有对应 attachment）追加到文件末尾
        added = 0
        for obj in snd_objects(scene):
            uid = int(obj.get("snd_uid", -1))
            if 0 <= uid < len(doc.attachments):
                continue
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
            doc.append_attachment(
                kind=kind, name=name,
                xyz=(loc[0] - origin[0], loc[1] - origin[1], loc[2] - origin[2]),
                remark=obj.name,
                the=obj.get("snd_the"), psi=obj.get("snd_psi"), phi=obj.get("snd_phi"),
                part=part, dref_idx=obj.get("snd_dref_idx"), flags=flags, conds=conds,
            )
            obj["snd_uid"] = int(doc.attachments[-1].index)
            added += 1

        try:
            write_file(self.filepath, doc)
        except OSError as exc:
            self.report({"ERROR"}, "写入失败: %s" % exc)
            return {"CANCELLED"}

        scene[PROP_PATH] = self.filepath
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


CLASSES = (IMPORT_OT_xplane_snd, EXPORT_OT_xplane_snd, SND_OT_solo, SND_OT_mute_all)
