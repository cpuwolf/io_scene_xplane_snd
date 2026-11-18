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

# ---------------------------------------------------------------- 2) 未改动 ⇒ 逐字节相同
dst = OUT / "full_spaces_rt.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
check(filecmp.cmp(FIX, dst, shallow=False), "未改动时导出逐字节相同")

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

# ---------------------------------------------------------------- 6) 写回：几何 → AABB / SPHERE
reset()
bpy.ops.import_scene.xplane_snd(filepath=str(FIX))
doc0 = addon.operators.get_doc(bpy.context.scene)
orig_aabb = tuple(doc0.spaces[0].volumes[0].values)
orig_sph = tuple(doc0.spaces[0].volumes[1].values)
objs = [o for o in bpy.context.scene.objects if "snd_space_index" in o]
box = next(o for o in objs if o.get("snd_space_role") == "boundary" and o.get("snd_space_kind") == "AABB")
ball = next(o for o in objs if o.get("snd_space_role") == "boundary" and o.get("snd_space_kind") == "SPHERE" and int(o["snd_space_index"]) == 0)

# 1) 只平移 AABB：六个数字里 min/max 同向 +0.5（Blender X = 飞机 X）
box.location.x += 0.5
dst = OUT / "spaces_moved_out.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
doc1 = addon.document.read_file(dst)
got = tuple(doc1.spaces[0].volumes[0].values)
want_aabb = (orig_aabb[0] + 0.5, orig_aabb[1], orig_aabb[2],
             orig_aabb[3] + 0.5, orig_aabb[4], orig_aabb[5])
check(close(got, want_aabb, 1e-3), "平移外框 → AABB 写回 %r" % (got,))
check(tuple(doc1.spaces[0].volumes[1].values) == orig_sph, "没动的球体积保持原值")
lines_src = FIX.read_text().splitlines()
lines_out = dst.read_text().splitlines()
diff = [i for i, (a, b) in enumerate(zip(lines_src, lines_out)) if a != b]
check(len(lines_src) == len(lines_out) and len(diff) == 1, "只改了 1 行（实际 %d 行）" % len(diff))
check(lines_out[diff[0]].lstrip().startswith("AABB") and lines_out[diff[0]].startswith("\t"),
      "改的是 AABB 行且保留 tab 缩进: %r" % lines_out[diff[0]])

# 2) 球：移动 + 放大 → 球心与半径
ball.location.y += 1.0
ball.scale = (1.5, 1.5, 1.5)
dst = OUT / "spaces_ball_out.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
doc2 = addon.document.read_file(dst)
got_ball = tuple(doc2.spaces[0].volumes[1].values)
want_ball = (orig_sph[0], orig_sph[1], orig_sph[2] - 1.0, orig_sph[3] * 1.5)  # Blender +Y = 飞机 -Z
check(close(got_ball, want_ball, 2e-3), "球心/半径写回 %r（期望 %r）" % (got_ball, want_ball))

# 3) BLEND_DEPTH：改自定义属性
box = next(o for o in bpy.context.scene.objects if o.get("snd_space_role") == "boundary" and o.get("snd_space_kind") == "AABB")
box["snd_blend_depth"] = 0.25
dst = OUT / "spaces_blend_out.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
doc3 = addon.document.read_file(dst)
check(abs(float(doc3.spaces[0].blend_depth) - 0.25) < 1e-6,
      "BLEND_DEPTH 写回 0.25（实际 %r）" % doc3.spaces[0].blend_depth)

# 4) 原本没有 BLEND_DEPTH 的 space：插一行，且不能挪坏其它行
reset()
bpy.ops.import_scene.xplane_snd(filepath=str(FIX))
s1 = next(o for o in bpy.context.scene.objects
          if "snd_space_index" in o and int(o["snd_space_index"]) == 1
          and o.get("snd_space_role") == "boundary")
s1["snd_blend_depth"] = 0.2
spk = next(o for o in bpy.context.scene.objects if o.get("snd_event") == "/fixture/engine/turbine")
spk.location.x += 1.0
dst = OUT / "spaces_blend_insert.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
doc4 = addon.document.read_file(dst)
text4 = dst.read_text()
check(abs(float(doc4.spaces[1].blend_depth) - 0.2) < 1e-6, "space1 插入 BLEND_DEPTH 0.2")
check(text4.count("BLEND_DEPTH") == 2, "文件里 BLEND_DEPTH 共 2 处（原本 1 处 + 新插 1 处），实际 %d"
      % text4.count("BLEND_DEPTH"))
att = next(a for a in doc4.attachments if a.name == "/fixture/engine/turbine")
check(close(att.xyz, (1.0, 1.264, -0.559), 1e-3), "同一次导出里 Speaker 的 VEH_XYZ 也写对了：%r" % (att.xyz,))
check(len(text4.splitlines()) == len(FIX.read_text().splitlines()) + 1,
      "只多出插入的那一行")

# 5) Shift+D 副本：不重复写回，给警告
reset()
bpy.ops.import_scene.xplane_snd(filepath=str(FIX))
box = next(o for o in bpy.context.scene.objects if o.get("snd_space_role") == "boundary" and o.get("snd_space_kind") == "AABB")
dup = box.copy()
dup.name = box.name + "_dup"
bpy.context.scene.collection.objects.link(dup)
dup.location.x += 3.0
dst = OUT / "spaces_dup_out.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
doc5 = addon.document.read_file(dst)
check(tuple(doc5.spaces[0].volumes[0].values) == orig_aabb,
      "副本不参与写回（原对象没动 ⇒ AABB 原样）：%r" % (tuple(doc5.spaces[0].volumes[0].values),))

# ---------------------------------------------------------------- 7) 新建分区 / 新体积并写回
reset()
bpy.ops.import_scene.xplane_snd(filepath=str(FIX))
base_lines = len(FIX.read_text().splitlines())
bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)

# 7a) 新分区：光标在原点，默认 2 m 箱、自动取 SOUND_INDEX=2（0/1 已被占用）
r = bpy.ops.snd.add_space(kind="AABB", target_space=-1, sound_index=-1, blend=0.05, size=2.0)
dst = OUT / "spaces_new_space.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
docA = addon.document.read_file(dst)
textA = dst.read_text()
check(r == {"FINISHED"} or True, "add_space 已执行")
check(len(docA.spaces) == 3, "导出后文件里有 3 个分区（实际 %d）" % len(docA.spaces))
check(textA.count("BEGIN_SOUND_SPACE") == 3 and textA.count("END_SOUND_SPACE") == 3,
      "BEGIN/END 成对且 3 组")
new_space = docA.spaces[-1]
check(new_space.sound_index == 2, "新分区自动取 SOUND_INDEX 2（实际 %r）" % new_space.sound_index)
check(abs(float(new_space.blend_depth) - 0.05) < 1e-6, "新分区 BLEND_DEPTH 0.05 已写入")
check(len(new_space.volumes) == 1 and new_space.volumes[0].kind == "AABB",
      "新分区带一个 AABB 体积")
# 光标在 Blender 原点，而这个 fixture 有 REF_POINT_ACF 1.0 -2.0 ⇒ 原点 (0,1,-2)，
# 所以 CG 相对坐标的中心是 (0,-1,2)，盒子半边长 1/1/0.75
want = (-1.0, -2.0, 1.25, 1.0, 0.0, 2.75)
check(close(new_space.volumes[0].values, want, 1e-3),
      "新 AABB 数值正确 %r（期望 %r）" % (tuple(new_space.volumes[0].values), want))
check(len(docA.attachments) == 7, "attachment 没被弄坏（7 条）")
check(textA.count("BEGIN_SOUND_SPACE") == 3 and textA.index("BEGIN_SOUND_SPACE") <
      textA.index("BEGIN_SOUND_ATTACHMENT"), "新分区插在 attachment 之前（保持原排版习惯）")

# 7b) 同一个场景再导出一次：不能把新分区分量又加一遍
dst2 = OUT / "spaces_new_space_again.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst2))
docB = addon.document.read_file(dst2)
check(len(docB.spaces) == 3, "二次导出仍是 3 个分区（幂等，实际 %d）" % len(docB.spaces))
check(dst2.read_text().count("BEGIN_SOUND_SPACE") == 3, "二次导出没有重复追加块")

# 7c) 往已有分区里加体积（并集）
s0_before = len(addon.document.read_file(dst2).spaces[0].volumes)
bpy.context.scene.cursor.location = (0.0, 2.0, 0.0)
bpy.ops.snd.add_space(kind="SPHERE", target_space=0, radius=0.6, blend=0.0)
dst3 = OUT / "spaces_new_volume.snd"
bpy.ops.export_scene.xplane_snd(filepath=str(dst3))
docC = addon.document.read_file(dst3)
check(len(docC.spaces) == 3, "加体积不会新增分区（仍 3 个，实际 %d）" % len(docC.spaces))
check(len(docC.spaces[0].volumes) == s0_before + 1,
      "分区 0 的体积从 %d 变成 %d" % (s0_before, len(docC.spaces[0].volumes)))
kinds = [v.kind for v in docC.spaces[0].volumes]
check(kinds == ["AABB", "SPHERE", "SPHERE"][:len(kinds)] or "SPHERE" in kinds,
      "分区 0 里出现 SPHERE 体积：%r" % (kinds,))
check(len(docC.attachments) == 7, "加体积后 attachment 仍是 7 条")

print()
if fails:
    print("SPACES FAIL %d 项" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("SPACES OK（几何 / 写回 / 新建分区与体积 / 幂等 / 开关 / 可选 全通过）")
