"""无头测试：.snd 的 Speaker 是否与 io_scene_xplane_obj 导入的网格对齐。

两种取网格的方式：
  1. 能 import io_scene_xplane_obj 且 XPlane2Blender 可用 → 用它真正的导入器（最有说服力）；
  2. 否则用本文件内置的 OBJ8 解析 + 同一个 xp_to_bl 变换（不依赖任何插件，CI 友好）。

判定：Speaker（XP2B 轴向）到网格曲面的距离——
  * 中位数 ≤ 15 cm
  * ≥ 90% 的点在 20 cm 内
（C90B 实测：中位 5.9 cm、84% 在 10 cm 内、开关类 0.0–0.1 cm）

  blender -b --factory-startup -P tests/align_mesh.py
"""
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HOME = Path(os.path.expanduser("~"))
sys.path.insert(0, str(HOME / "GitHub"))
import io_scene_xplane_snd as addon  # noqa: E402
from io_scene_xplane_snd import acftool  # noqa: E402

addon.register()

AC = HOME / "X-Plane 12/Aircraft/Laminar Research/Beechcraft King Air C90B"
SND = AC / "fmod/C90B.snd"
OBJS = [AC / "C90B_cockpit.obj"] + sorted((AC / "objects/C90B_cockpit").glob("*.obj"))


def say(*a):
    print("ALIGN", *a, flush=True)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


clear()

# ---------------- 取网格 ----------------
used = None
try:
    import io_scene_xplane_obj as xpobj
    import io_scene_xplane_obj.xp2b as xp2b
    if xp2b.available():
        xpobj.register()
        # 必须把座舱的 9 个 OBJ 全导进来 —— 只导根目录那个大文件会缺面板/中控台几何，
        # 点到曲面的距离会被高估（这是第一次跑出 FAIL 的真实原因：网格不全，不是变换错）。
        for f in OBJS:
            bpy.ops.import_scene.xplane_obj(filepath=str(f))
        used = "io_scene_xplane_obj (%d files)" % len(OBJS)
except Exception as exc:  # noqa: BLE001
    say("插件导入不可用（%s）" % type(exc).__name__)

if used is None:
    verts, faces = [], []
    for f in OBJS:
        txt = f.read_text(errors="ignore")
        base = len(verts)
        for line in txt.splitlines():
            if line[:2] == "VT":
                p = line.split()
                if len(p) >= 4:
                    verts.append(acftool.xp_to_bl((float(p[1]), float(p[2]), float(p[3]))))
        for line in txt.splitlines():
            if line.startswith("IDX10"):
                q = line.split()
                i = [int(x) for x in q[1:11]]
                faces.append((base + i[0], base + i[1], base + i[2]))
    me = bpy.data.meshes.new("cabin")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("cabin", me)
    bpy.context.scene.collection.objects.link(ob)
    used = "own parser + xp_to_bl"
say("mesh source:", used)

# BVH（世界坐标）
verts_w, faces_l = [], []
base = 0
for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
    mw = o.matrix_world
    vs = [mw @ v.co for v in o.data.vertices]
    verts_w.extend(vs)
    for poly in o.data.polygons:
        faces_l.append(tuple(base + i for i in poly.vertices))
    base += len(vs)
bvh = BVHTree.FromPolygons(verts_w, faces_l, all_triangles=False)
say("bvh verts=%d faces=%d" % (len(verts_w), len(faces_l)))

# ---------------- 导入 .snd（XP2B 轴向） ----------------
AXIS = "RAW" if "--raw" in sys.argv else "XP2B"   # --raw 是负向对照：不做轴向映射，应该明显更差
bpy.ops.import_scene.xplane_snd(filepath=str(SND), axis_mode=AXIS)
say("snd axis:", AXIS)
spk = [o for o in bpy.context.scene.objects if o.type == "SPEAKER"]
say("speakers=%d" % len(spk))

pairs = sorted(((bvh.find_nearest(o.location)[3], o) for o in spk), key=lambda t: t[0])
d = [p[0] for p in pairs]


def q(f):
    return d[min(len(d) - 1, int(len(d) * f))]


say("DIST min=%.4f p50=%.3f p90=%.3f max=%.3f" % (d[0], q(.5), q(.9), d[-1]))
for thr in (.01, .05, .10, .20):
    n = sum(1 for x in d if x <= thr)
    say("  <=%.2fm: %d/%d (%.0f%%)" % (thr, n, len(d), 100.0 * n / len(d)))

# 开关类最该贴合
switch = [x for x in pairs if str(x[1].get("snd_event", "")).startswith("/model/kingair_c90b/switches/")]
if switch:
    sw = sorted(x[0] for x in switch)
    say("switches: n=%d median=%.4f m worst=%.4f m" % (len(sw), sw[len(sw) // 2], sw[-1]))

ok = q(.5) <= 0.15 and sum(1 for x in d if x <= 0.20) >= 0.9 * len(d)
if AXIS == "RAW":
    # 负向对照：RAW 与导入网格不同轴，应当 PASS 不了
    say("VERDICT(negative control, expect FAIL):", "PASS(?! unexpected)" if ok else "FAIL as expected")
else:
    say("VERDICT:", "PASS" if ok else "FAIL")
say("DONE")
