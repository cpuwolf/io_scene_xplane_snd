"""冒烟测试：扩展能被 Blender 加载、算子已注册。

CI 里在 `blender --command extension install-file -r user_default -e` 之后跑，
用来验证"用户装完之后确实能用"这条路径。

  blender -b --python tests/smoke.py
"""
import sys

import bpy

ADDON_ID = "bl_ext.user_default.io_scene_xplane_snd"

enabled = ADDON_ID in bpy.context.preferences.addons
import_ok = hasattr(bpy.ops.import_scene, "xplane_snd")
export_ok = hasattr(bpy.ops.export_scene, "xplane_snd")
panel = hasattr(bpy.types, "SND_PT_panel")

print("SMOKE enabled=%s import=%s export=%s panel=%s" % (enabled, import_ok, export_ok, panel), flush=True)

if not (enabled and import_ok and export_ok):
    print("SMOKE 失败：扩展没装好或算子没注册", flush=True)
    sys.exit(1)
print("SMOKE OK", flush=True)
