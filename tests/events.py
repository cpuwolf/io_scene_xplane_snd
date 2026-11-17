"""事件（EVENT_NAME）与 attachment 的 1:N 关系必须能在 Blender 里看到、改得动、写得回。

覆盖：
1. 导入后每个事件一个 Collection，成员数等于 .snd 里同名 attachment 的数量；
2. 面板数据源 Scene.snd_events 的条目数 == 不同事件名数量，count 之和 == attachment 数；
3. snd.rename_event 改整组 → 导出后 .snd 里对应那一行跟着变，其余 attachment 不动。
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

import io_scene_xplane_snd as addon                      # noqa: E402
from io_scene_xplane_snd.document import read_file      # noqa: E402

addon.register()

FIXTURE = HERE / "fixtures" / "events.snd"


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)


def main():
    if not FIXTURE.is_file():
        print("EVENTS skip（fixtures 未生成，先跑 tests/make_fixtures.py）")
        return 0
    clear()
    doc = read_file(FIXTURE)
    want = {}
    for att in doc.attachments:
        if att.name:
            want[att.name] = want.get(att.name, 0) + 1
    if not any(v > 1 for v in want.values()):
        print("EVENTS skip（fixtures 里没有重复事件名，测不出 1:N）")
        return 0

    bpy.ops.import_scene.xplane_snd(filepath=str(FIXTURE))
    problems = []

    # 1) collection 分组
    parent = bpy.data.collections.get("SND " + FIXTURE.name)
    if parent is None:
        problems.append("没有建顶层 collection")
    else:
        kids = {c.get("snd_event"): len(c.objects) for c in parent.children}
        if len(kids) != len(want):
            problems.append("collection 数 %d != 事件数 %d" % (len(kids), len(want)))
        for name, n in want.items():
            if kids.get(name) != n:
                problems.append("%s 的 collection 有 %r 个对象，期望 %d" % (name, kids.get(name), n))

    # 2) 面板数据源
    items = {it.event: it.count for it in bpy.context.scene.snd_events}
    if items != want:
        problems.append("Scene.snd_events 与文件里的分组不一致: %r vs %r" % (items, want))

    # 3) 整组改名 + 写回
    target = next((n for n, c in want.items() if c > 1), None)
    new_name = "/test/renamed_%d" % want[target]
    bpy.context.scene.snd_events_index = [it.event for it in bpy.context.scene.snd_events].index(target)
    bpy.context.scene.snd_event_new = new_name
    if "FINISHED" not in bpy.ops.snd.rename_event():
        problems.append("rename_event 被取消")
    out = pathlib.Path(tempfile.mkdtemp()) / "renamed.snd"
    bpy.ops.export_scene.xplane_snd(filepath=str(out))
    after = read_file(out)
    names = [a.name for a in after.attachments]
    if names.count(new_name) != want[target]:
        problems.append("写回后 %s 出现 %d 次，期望 %d" % (new_name, names.count(new_name), want[target]))
    if target in names:
        problems.append("旧名字 %s 还留在文件里" % target)
    if len(after.attachments) != len(doc.attachments):
        problems.append("attachment 数变了：%d -> %d" % (len(doc.attachments), len(after.attachments)))
    # 其余行不受影响
    for i, att in enumerate(doc.attachments):
        if att.name == target:
            continue
        if i < len(after.attachments) and after.attachments[i].name != att.name:
            problems.append("第 %d 个 attachment 的名字被牵连改动了" % i)
            break

    print("EVENTS %s（%d 个事件 / %d 个 attachment；1:N 样本 %s x%d）" % (
        "ok" if not problems else "bad", len(want), len(doc.attachments), target, want[target]))
    for p in problems:
        print("  - " + p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
