"""io_scene_xplane_snd — X-Plane .snd 的导入 / 导出 / 试听。

刻意零依赖：
  * 不用 XPlane2Blender（不碰 bpy.types.Object.xplane、不调 export_scene.xplane）；
  * 不用 io_scene_xplane_obj；
  * 只用 Blender 自带 API + Python 标准库，所以 `blender -b` 下也能完整跑回归测试。

导出采用"保留原文、只 patch 改动行"的策略：没动过的文件写回后与输入逐字节相同。
"""
from __future__ import annotations

import sys

import bpy

from . import operators, ui
from .operators import (
    EXPORT_OT_xplane_snd,
    IMPORT_OT_xplane_snd,
    SND_OT_mute_all,
    SND_OT_solo,
)

bl_info = {
    "name": "X-Plane SND (.snd) Import/Export",
    "author": "cpuwolf",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "File > Import/Export > X-Plane SND；3D 视图侧栏 X-Plane > X-Plane SND",
    "description": "导入/导出 X-Plane .snd（每个 attachment 一个 Speaker，可 solo 试听），不依赖 XPlane2Blender",
    "category": "Import-Export",
}


def _menu_import(self, context):
    self.layout.operator(IMPORT_OT_xplane_snd.bl_idname, text="X-Plane SND (.snd)")


def _menu_export(self, context):
    self.layout.operator(EXPORT_OT_xplane_snd.bl_idname, text="X-Plane SND (.snd)")


CLASSES = operators.CLASSES + ui.CLASSES


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(_menu_import)
    bpy.types.TOPBAR_MT_file_export.append(_menu_export)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_menu_import)
    bpy.types.TOPBAR_MT_file_export.remove(_menu_export)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
