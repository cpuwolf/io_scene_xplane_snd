"""无头测试：原点解析（REF_POINT_ACF / .acf 默认 CG / 兜底）。

不碰 X-Plane 安装目录：全部在临时目录里造 .acf 和 .snd。

  blender -b --factory-startup -P tests/origin.py
"""
import os
import sys
import tempfile
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
sys.path.insert(0, str(HOME / "GitHub"))
from io_scene_xplane_snd import acftool  # noqa: E402
from io_scene_xplane_snd.document import Document  # noqa: E402

FEET = 0.3048
fails = []


def say(*a):
    print("ORIGIN", *a, flush=True)


def check(name, got, want, tol=1e-4):
    ok = got is not None and all(abs(g - w) <= tol for g, w in zip(got, want)) and len(got) == len(want)
    say("%-34s %s  got=%s want=%s" % (name, "OK  " if ok else "FAIL",
                                     None if got is None else tuple(round(v, 4) for v in got),
                                     tuple(round(v, 4) for v in want)))
    if not ok:
        fails.append(name)


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp / "fmod").mkdir()

    # --- 1. REF_POINT_ACF 优先（米，直接给 y/z） ---
    snd = tmp / "fmod" / "ref.snd"
    snd.write_text("A\n1000\nACF_SOUNDS\nREF_POINT_ACF 1.0 -2.0\n")
    origin, src, warn = acftool.resolve_origin(Document(snd.read_text()), snd)
    check("REF_POINT_ACF", origin, (0.0, 1.0, -2.0))
    say("  source=%s warn=%s" % (src, warn))
    if src != "ref_point_acf":
        fails.append("REF_POINT source")

    # --- 2. 没有 REF_POINT_ACF → 读 .acf 的默认 CG（英尺 → 米） ---
    (tmp / "plane.acf").write_text(
        "P acf/_cgX_lft -0.010000000\n"
        "P acf/_cgX_rgt 0.010000000\n"
        "P acf/_cgY 0.250000000\n"
        "P acf/_cgZ 11.449999809\n"
    )
    snd2 = tmp / "fmod" / "cg.snd"
    snd2.write_text("A\n1000\nACF_SOUNDS\n")
    origin, src, warn = acftool.resolve_origin(Document(snd2.read_text()), snd2)
    check("acf 默认 CG", origin, (0.0, 0.25 * FEET, 11.45 * FEET))
    say("  source=%s warn=%s" % (src, warn))
    if not str(src).startswith("acf_cg"):
        fails.append("acf_cg source")

    # --- 3. .acf 里没有 _cgY/_cgZ → 兜底 + 警告 ---
    (tmp / "plane.acf").write_text("P acf/_m_empty 100\n")
    snd3 = tmp / "fmod" / "nothing.snd"
    snd3.write_text("A\n1000\nACF_SOUNDS\n")
    origin, src, warn = acftool.resolve_origin(Document(snd3.read_text()), snd3)
    check("acf 缺键", origin, (0.0, 0.0, 0.0))
    say("  source=%s warn=%s" % (src, warn))
    if not warn:
        fails.append("missing warning")

    # --- 4. 完全找不到 .acf → 兜底 + 警告（先把上面造的 plane.acf 删掉） ---
    (tmp / "plane.acf").unlink()
    orphan = tmp / "lonely"
    orphan.mkdir()
    snd4 = orphan / "x.snd"
    snd4.write_text("A\n1000\nACF_SOUNDS\n")
    origin, src, warn = acftool.resolve_origin(Document(snd4.read_text()), snd4)
    check("无 .acf", origin, (0.0, 0.0, 0.0))
    say("  source=%s warn=%s" % (src, warn))
    if not warn:
        fails.append("missing warning 2")

# --- 5. 轴向变换往返 ---
for p in ((1.0, 2.0, 3.0), (-0.5, 1.4, -2.0), (0.0, 0.0, 0.0)):
    back = acftool.from_blender(acftool.to_blender(p, "XP2B"), "XP2B")
    check("axis roundtrip %s" % (p,), back, p)
    check("axis identity RAW %s" % (p,), acftool.to_blender(p, "RAW"), p)

say("FAILS: %d %s" % (len(fails), fails if fails else ""))
say("DONE")
