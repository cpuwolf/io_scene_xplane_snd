"""无头回归测试：import → export 必须逐字节等于源文件（不依赖 XP2B）。

用法：
  blender -b --factory-startup -P tests/roundtrip.py -- [额外文件...]
默认扫 X-Plane 12 下所有 .snd。
"""
import os
import sys
import glob
from pathlib import Path

import bpy

HOME = Path(os.path.expanduser("~"))
ADDON_PARENT = HOME / "GitHub"
if str(ADDON_PARENT) not in sys.path:
    sys.path.insert(0, str(ADDON_PARENT))

import io_scene_xplane_snd as addon  # noqa: E402

addon.register()

OUT = Path("/tmp/sndtest/out")
OUT.mkdir(parents=True, exist_ok=True)


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for spk in list(bpy.data.speakers):
        bpy.data.speakers.remove(spk)


def roundtrip(src: Path, axis="XP2B"):
    clear()
    bpy.ops.import_scene.xplane_snd(filepath=str(src), axis_mode=axis)
    n = len([o for o in bpy.context.scene.objects if "snd_uid" in o])
    dst = OUT / (src.stem + "__rt.snd")
    bpy.ops.export_scene.xplane_snd(filepath=str(dst))
    a = src.read_bytes()
    b = dst.read_bytes()
    return n, a == b, len(a), len(b)


def move_one(src: Path, delta=0.1, axis="XP2B"):
    """改一个 Speaker 的位置，导出的 diff 应该只有 1 行。"""
    clear()
    bpy.ops.import_scene.xplane_snd(filepath=str(src), axis_mode=axis)
    objs = sorted([o for o in bpy.context.scene.objects if "snd_uid" in o],
                  key=lambda o: int(o.get("snd_uid", 0)))
    if not objs:
        return None
    target = None
    for o in objs:
        if o.get("snd_has_xyz"):
            target = o
            break
    if target is None:
        return None
    target.location.y += delta
    dst = OUT / (src.stem + "__moved.snd")
    bpy.ops.export_scene.xplane_snd(filepath=str(dst))
    la = src.read_text(errors="surrogateescape").splitlines()
    lb = dst.read_text(errors="surrogateescape").splitlines()
    diff = [(i, x, y) for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    return len(la) == len(lb), diff


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    axis = "RAW" if "--raw" in argv else "XP2B"
    argv = [a for a in argv if not a.startswith("--")]
    print("AXIS", axis, flush=True)
    if argv:
        files = [Path(p) for p in argv]
    else:
        root = HOME / "X-Plane 12"
        files = sorted(root.rglob("*.snd"))

    ok = bad = 0
    for f in files:
        try:
            n, same, sa, sb = roundtrip(f, axis)
        except Exception as exc:  # noqa: BLE001
            print("ERR  %-46s %r" % (f.name[:46], exc), flush=True)
            bad += 1
            continue
        print("%s %-46s speakers=%-5d bytes %d/%d" % (
            "OK  " if same else "DIFF", f.name[:46], n, sa, sb), flush=True)
        ok += same
        bad += (not same)

    print("\nROUNDTRIP: %d ok / %d bad / %d files" % (ok, bad, len(files)), flush=True)

    # 改一个点，验证 patch 只动一行
    probe = HOME / "X-Plane 12/Aircraft/Laminar Research/Beechcraft King Air C90B/fmod/C90B.snd"
    if probe.is_file():
        res = move_one(probe, axis=axis)
        if res:
            same_len, diff = res
            print("PATCH line count same=%s, changed lines=%d" % (same_len, len(diff)), flush=True)
            for i, x, y in diff[:3]:
                print("   L%-5d - %s" % (i + 1, x.strip()), flush=True)
                print("   L%-5d + %s" % (i + 1, y.strip()), flush=True)
    print("DONE", flush=True)


main()
