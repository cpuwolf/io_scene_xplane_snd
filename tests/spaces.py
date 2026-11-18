"""sound space（AABB / SPHERE）可视化回归测试。

fixtures/full.snd 里有两个 space：
  0: SOUND_INDEX 0, BLEND_DEPTH 0.03, AABB + SPHERE（并集）
  1: SOUND_INDEX 1, 只有一个 SPHERE，没有 blend
文件里还有 REF_POINT_ACF 1.0 -2.0，所以原点 = (0, 1.0, -2.0)。

  blender -b --factory-startup -P tests/spaces.py
"""
import filecmp
import math
import os
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "full.snd"
# 让 checkout 目录本身作为包的父目录进 sys.path（目录名 == 包名，CI 的 checkout 也一样）
sys.path.insert(0, str(HERE.parent.parent))

import io_scene_xplane_snd as addon  # noqa: E402

addon.register()

OUT = Path("/tmp/sndtest/out")
OUT.mkdir(parents=True, exist_ok=True)
fails = []


def check(cond, msg):
    print("%s %s" % ("OK  " if cond else "FAIL", msg))
    if not cond:
        fails.append(msg)


def close(a, b, tol=1e-3):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def world_extent(obj):
    """网格顶点的世界坐标轴对齐包围盒尺寸（不含 Wireframe 修改器 —— 那只是画法）。"""
    mw = obj.matrix_world
    pts = [mw @ v.co for v in obj.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return tuple(hi[i] - lo[i] for i in range(3))


def reset():
    addon.unregister()
    bpy.ops.wm.read_homefile(use_empty=True)
    addon.register()


# ---------------------------------------------------------------- 1) 对象结构与几何
reset()
res = bpy.ops.import_scene.xplane_snd(filepath=str(FIX))
check(res == {"FINISHED"}, "import FINISHED")

objs = [o for o in bpy.context.scene.objects if "snd_space_index" in o]
check(len(objs) == 5, "5 个 space 对象（space0 = AABB+球 各带 core，space1 = 一个球）实际 %d" % len(objs))

space0 = [o for o in objs if int(o["snd_space_index"]) == 0]
space1 = [o for o in objs if int(o["snd_space_index"]) == 1]
check(len(space0) == 4 and len(space1) == 1,
      "space0=4 / space1=1（实际 %d / %d）" % (len(space0), len(space1)))

roles = sorted((o.get("snd_space_kind"), o.get("snd_space_role")) for o in space0)
check(roles == [("AABB", "boundary"), ("AABB", "core"), ("SPHERE", "boundary"), ("SPHERE", "core")],
      "space0 的 kind/role 组合：%r" % (roles,))

box = next(o for o in space0 if o.get("snd_space_kind") == "AABB" and o.get("snd_space_role") == "boundary")
box_core = next(o for o in space0 if o.get("snd_space_kind") == "AABB" and o.get("snd_space_role") == "core")
sph = next(o for o in space0 if o.get("snd_space_kind") == "SPHERE" and o.get("snd_space_role") == "boundary")
sph1 = space1[0]

# AABB 在飞机坐标里是 (-0.8, 0.1, -1.183) … (0.8, 1.57, 3.917)，轴向映射后
# Blender 的 (x, y, z) = (x, -z, y) → 尺寸 (1.6, 5.1, 1.47)
want = (1.6, 3.917 + 1.183, 1.57 - 0.1)
got = world_extent(box)
check(close(got, want, 2e-3), "AABB 外框尺寸 %.3f,%.3f,%.3f vs 期望 %.3f,%.3f,%.3f"
      % (got + want))
core_got = world_extent(box_core)
check(close(core_got, tuple(w - 0.06 for w in want), 2e-3),
      "BLEND_DEPTH 0.03 让 core 每一维小 0.06 m（%.3f vs %.3f）"
      % (core_got[0], want[0] - 0.06))

# SPHERE 在 space0 里是 (0, 1.2, -1.5) r=0.9，加原点 (0,1,-2) → Blender (0, 3.5, 2.2)
check(close(sph.location, (0.0, 3.5, 2.2), 1e-3), "球心随原点和轴向换算正确：%r" % (tuple(sph.location),))
check(close(world_extent(sph), (1.8, 1.8, 1.8), 5e-3),
      "球直径 = 2r：%.3f" % world_extent(sph)[0])
check(close(sph1.location, (1.0, 0.0, 1.5), 1e-3), "没 blend 的 space1 球心：%r" % (tuple(sph1.location),))

check(all(o.show_in_front for o in objs), "全部 space 对象 show_in_front（座舱里也看得见）")
check(all(any(m.type == "WIREFRAME" for m in o.modifiers) for o in objs), "都有 Wireframe 修改器（颜色才看得见）")
check(all("snd_uid" not in o for o in objs), "space 对象没有 snd_uid（不会被当成 attachment 导出）")

# ---------------------------------------------------------------- 2) 只读：改框不写回
dst = OUT / "full_spaces_rt.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
check(filecmp.cmp(FIX, dst, shallow=False), "未改动时导出逐字节相同")

box.location = (5.0, 5.0, 5.0)
box.scale = (2.0, 2.0, 2.0)
sph1.location = (-3.0, 0.0, 0.0)
dst2 = OUT / "full_spaces_moved.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst2))
check(filecmp.cmp(FIX, dst2, shallow=False), "挪动/缩放 space 框后导出仍逐字节相同（只读）")

# ---------------------------------------------------------------- 3) 开关
r = bpy.ops.snd.toggle_spaces()
colls = [c for c in bpy.data.collections if c.name.endswith(" / Sound spaces")]
check(r == {"FINISHED"} and colls and all(c.hide_viewport for c in colls), "toggle 隐藏了 space 集合")
r = bpy.ops.snd.toggle_spaces()
check(r == {"FINISHED"} and all(not c.hide_viewport for c in colls), "再 toggle 回来")

# ---------------------------------------------------------------- 4) 可以不建
reset()
bpy.ops.import_scene.xplane_snd(filepath=str(FIX), make_spaces=False)
check(len([o for o in bpy.context.scene.objects if "snd_space_index" in o]) == 0,
      "make_spaces=False 时一个 space 对象都不建")

# ---------------------------------------------------------------- 5) 没有 space 的文件
reset()
plain = HERE / "fixtures" / "events.snd"
bpy.ops.import_scene.xplane_snd(filepath=str(plain))
check(len([o for o in bpy.context.scene.objects if "snd_space_index" in o]) == 0,
      "没有 sound space 的文件不受影响")

print()
if fails:
    print("SPACES FAIL %d 项" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("SPACES OK（几何 / 只读 / 开关 / 可选 全通过）")
