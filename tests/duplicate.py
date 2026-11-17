"""Shift+D 复制 Speaker 之后导出：副本必须变成新增 attachment，原块不动。

用 tests/fixtures/full.snd（自制，无任何 Laminar 素材）。
"""
import os
import pathlib
import sys
import tempfile

import bpy

HERE = pathlib.Path(__file__).resolve().parent
HOME = pathlib.Path(os.path.expanduser("~"))
for p in (str(HOME / "GitHub"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import io_scene_xplane_snd as addon            # noqa: E402
from io_scene_xplane_snd.document import read_file  # noqa: E402

addon.register()

FIXTURE = HERE / "fixtures" / "full.snd"


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def snapshot(att):
    return (att.kind, att.name, att.xyz, att.the, att.psi, att.phi,
            att.part, att.dref_idx, tuple(att.flags), tuple(att.conds))


def main():
    if not FIXTURE.is_file():
        print("DUPLICATE skip（fixtures 未生成，先跑 tests/make_fixtures.py）")
        return 0
    clear()
    bpy.ops.import_scene.xplane_snd(filepath=str(FIXTURE))
    speakers = sorted((o for o in bpy.context.scene.objects if o.type == "SPEAKER"),
                      key=lambda o: int(o.get("snd_uid", 0)))
    if not speakers:
        print("DUPLICATE bad：导入后没有 Speaker")
        return 1

    before = read_file(FIXTURE)
    src = speakers[0]
    uid = int(src.get("snd_uid"))
    new_name = "/test/duplicate_of_%d" % uid

    # 模拟 Shift+D：共享同一个 Speaker 数据块，custom properties 复制过来
    dup = bpy.data.objects.new(src.name + "_copy", src.data)
    bpy.context.scene.collection.objects.link(dup)
    dup.location = src.location
    for key in src.keys():
        dup[key] = src[key]
    dup["snd_event"] = new_name
    shared_data = dup.data == src.data

    out = pathlib.Path(tempfile.mkdtemp()) / "dup.snd"
    bpy.ops.export_scene.xplane_snd(filepath=str(out))
    after = read_file(out)

    problems = []
    if len(after.attachments) != len(before.attachments) + 1:
        problems.append("附件数 %d -> %d（期望 +1，副本被吞了）"
                        % (len(before.attachments), len(after.attachments)))
    if [a.name for a in after.attachments].count(new_name) != 1:
        problems.append("新块没写进文件（期望出现一次 %s）" % new_name)
    for i, att in enumerate(before.attachments):
        if i >= len(after.attachments):
            break
        if snapshot(att) != snapshot(after.attachments[i]):
            problems.append("第 %d 个 attachment 被改动了" % i)
            break
    if int(dup.get("snd_uid")) != len(after.attachments) - 1:
        problems.append("副本导出后没拿到新的 snd_uid")

    print("DUPLICATE %s（%d -> %d 个附件，Speaker data 共享=%s）" % (
        "ok" if not problems else "bad",
        len(before.attachments), len(after.attachments), shared_data))
    for p in problems:
        print("  - " + p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
