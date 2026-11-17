"""诊断脚本：确认 .snd 拖拽导入的注册状态。

用法（二选一）：
  * Blender 里：Scripting 工作区 → 打开本文件 → Run Script，输出在 System Console / Info；
  * 命令行：blender -b --python tests/diagnose.py
"""
import bpy

MOD = "bl_ext.user_default.io_scene_xplane_snd"
lines = []

addons = list(bpy.context.preferences.addons.keys())
lines.append("已启用扩展: %s" % ("YES" if MOD in addons else "NO (%s)" % ", ".join(
    a for a in addons if "xplane" in a or "snd" in a)))

has_ops = hasattr(bpy.ops.import_scene, "xplane_snd")
lines.append("import_scene.xplane_snd: %s" % has_ops)

fh = getattr(bpy.types, "SND_FH_import", None)
if fh is None:
    lines.append("FileHandler: 未注册 —— 拖拽必然无效")
else:
    lines.append("FileHandler: %s" % fh.bl_idname)
    lines.append("  bl_file_extensions = %r" % getattr(fh, "bl_file_extensions", None))
    lines.append("  bl_import_operator = %r" % getattr(fh, "bl_import_operator", None))
    poll = getattr(fh, "poll_drop", None)
    lines.append("  poll_drop 存在: %s" % bool(poll))
    if poll:
        lines.append("  poll_drop(None) = %s" % poll(None))

try:
    lines.append("当前上下文 area = %r · space_data = %r" % (
        getattr(bpy.context, "area", None) and bpy.context.area.type,
        getattr(bpy.context, "space_data", None) and bpy.context.space_data.type))
except Exception as exc:  # noqa: BLE001
    lines.append("上下文读取失败: %r" % exc)

text = "\n".join(lines)
print("---- diagnose ----", flush=True)
print(text, flush=True)
print("------------------", flush=True)

# GUI 里跑时顺便弹窗，方便截图
try:
    if bpy.context.area and bpy.context.area.type != "CONSOLE":
        bpy.context.window_manager.popup_menu(
            lambda self, ctx: [self.layout.label(text=l) for l in lines],
            title="X-Plane SND 诊断", icon="INFO")
except Exception:
    pass
