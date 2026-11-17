"""冒烟测试：扩展能被 Blender 加载、算子已注册。

CI 里在 `blender --command extension install-file -r user_default -e` 之后跑，
用来验证"用户装完之后确实能用"这条路径。

  blender -b --python tests/smoke.py
"""
import pathlib
import sys

import bpy

ADDON_ID = "bl_ext.user_default.io_scene_xplane_snd"

enabled = ADDON_ID in bpy.context.preferences.addons
import_ok = hasattr(bpy.ops.import_scene, "xplane_snd")
export_ok = hasattr(bpy.ops.export_scene, "xplane_snd")
panel = hasattr(bpy.types, "SND_PT_panel")
fh = getattr(bpy.types, "SND_FH_import", None)
fh_ext = getattr(fh, "bl_file_extensions", "") if fh else ""

print("SMOKE enabled=%s import=%s export=%s panel=%s filehandler=%r" % (
    enabled, import_ok, export_ok, panel, fh_ext), flush=True)

if ".snd" not in (fh_ext or ""):
    print("SMOKE 失败：FileHandler 没注册（拖拽 .snd 不会生效）", flush=True)
    sys.exit(1)

# 模拟"拖拽导入"：Blender 的 FileHandler 会带 files 列表调 INVOKE_DEFAULT，
# 我们的 invoke 在这里应该直接 execute，不弹文件对话框。
drop_ok = None
fixture = pathlib.Path(__file__).resolve().parent / "fixtures" / "full.snd"
if fixture.is_file():
    res = bpy.ops.import_scene.xplane_snd(
        "INVOKE_DEFAULT", filepath=str(fixture), files=[{"name": fixture.name}])
    n = len([o for o in bpy.context.scene.objects if "snd_uid" in o])
    drop_ok = (res == {"FINISHED"} and n == 7)
    print("SMOKE dragdrop=%s speakers=%d (期望 FINISHED / 7)" % (res, n), flush=True)
    if not drop_ok:
        print("SMOKE 失败：拖拽路径没有直接导入（可能弹了对话框）", flush=True)
        sys.exit(1)
else:
    print("SMOKE dragdrop skipped (fixtures 未生成)", flush=True)

if not (enabled and import_ok and export_ok):
    print("SMOKE 失败：扩展没装好或算子没注册", flush=True)
    sys.exit(1)
print("SMOKE OK", flush=True)
