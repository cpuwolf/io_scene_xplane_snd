"""把 .snd 拖进 Blender 3D 视图 / 文件浏览器时的处理器。

Blender 的拖拽导入靠 `FileHandler`（4.2+ 都是这个机制）：
只要注册一个带 `bl_file_extensions` 的 FileHandler，并指向我们的导入算子，
把文件从 Finder / Explorer 拖进视口就会走 `import_scene.xplane_snd`。
"""
from __future__ import annotations

import bpy


class SND_FH_import(bpy.types.FileHandler):
    bl_idname = "SND_FH_import"
    bl_label = "X-Plane SND (.snd)"
    bl_import_operator = "import_scene.xplane_snd"
    bl_file_extensions = ".snd"


CLASSES = (SND_FH_import,)
