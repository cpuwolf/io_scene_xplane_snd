"""无头测试（变更路径）：新增 attachment + 给已有 attachment 插入 VEH_THE。

验证三件事：
  1. 新 Speaker（snd_uid = -1）导出后变成一条新的 BEGIN/END 块，含 THE/PSI/条件；
  2. 给原本没有 VEH_THE 的 attachment 设值，导出会在正确位置插入一行；
  3. 导出的新文件能被重新解析，且二次渲染自一致。

  blender -b --factory-startup -P tests/mutation.py
"""
import os
import sys
from pathlib import Path

import bpy
HOME = Path(os.path.expanduser("~"))
sys.path.insert(0, str(HOME / "GitHub"))
import io_scene_xplane_snd as addon
addon.register()
sys.path.insert(0, str(HOME / "GitHub/io_scene_xplane_snd"))
from document import Document

SRC = HOME / "X-Plane 12/Aircraft/Laminar Research/Beechcraft King Air C90B/fmod/C90B.snd"
def say(*a): print("EXTRA", *a, flush=True)
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.xplane_snd(filepath=str(SRC))

# 1) 新 Speaker，带朝向 + 条件
sp = bpy.data.speakers.new("n1"); sp.muted = True
o = bpy.data.objects.new("SND_new_test", sp)
bpy.context.scene.collection.objects.link(o)
o.location = (1.0, 0.5, 3.9)
o["snd_uid"] = -1; o["snd_kind"] = "event"; o["snd_event"] = "/model/test/new_sound"
o["snd_has_xyz"] = True; o["snd_the"] = 12.5; o["snd_psi"] = -30.0
o["snd_conds"] = "EVENT_START_COND sim/test/dref > 1\nEVENT_END_COND sim/test/dref == 0"

# 2) 老的 attachment（uid>=0）原本没 VEH_THE，加一个
victim = None
for ob in sorted(bpy.context.scene.objects, key=lambda x: int(x.get("snd_uid", 99999))):
    if int(ob.get("snd_uid", -1)) >= 0 and ob.get("snd_has_xyz") and "snd_the" not in ob:
        victim = ob; break
say("victim:", victim.name if victim else None, "uid", victim.get("snd_uid") if victim else None)
if victim: victim["snd_the"] = 7.5

dst = Path("/tmp/sndtest/extra2.snd")
bpy.ops.export_scene.xplane_snd(filepath=str(dst))
txt = dst.read_text(errors="surrogateescape")
doc = Document(txt)
say("attachments=%d (期望 437)" % len(doc.attachments))
last = doc.attachments[-1]
say("新增块:", last.kind, last.name, "xyz=%s the=%s psi=%s conds=%d" % (last.xyz, last.the, last.psi, len(last.conds)))
if victim:
    same = [a for a in doc.attachments if a.name == victim.get("snd_event")]
    say("受害者同名 attachment %d 个，其中带 THE 的: %d" % (len(same), sum(1 for a in same if a.the is not None)))
    say("插入的 THE 值:", [a.the for a in same if a.the is not None][:3])
say("新文件可再解析且自一致:", Document(txt).render() == txt)
say("尾部 8 行:")
for l in txt.splitlines()[-8:]: say("   ", l)
say("DONE")
