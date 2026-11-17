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
    # 多个扩展名用 ";" 分隔（Blender 自带 handler 都是这么拼的）
    bl_file_extensions = ".snd"

    @classmethod
    def poll_drop(cls, context):
        """拖放时是否接受这个文件。

        这个方法**必须存在** —— 没有 poll_drop 的 FileHandler 只会出现在 Import 菜单/
        文件浏览器里，拖进视口不会有任何反应（这正是之前拖拽"没反应"的原因）。
        我们只认 .snd，不存在与内置 handler 竞争，所以任何区域都放行。
        """
        if context is None:          # 某些调用路径（含测试）会传 None
            return True
        return (getattr(context, "area", None) is not None
                or getattr(context, "space_data", None) is not None)


CLASSES = (SND_FH_import,)
