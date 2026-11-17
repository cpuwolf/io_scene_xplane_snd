"""从 .acf / .snd 里算出 .snd 坐标的原点。

.snd 的 VEH_XYZ 是"相对原点"的米制坐标，原点有两种可能：
  1. 文件里有 REF_POINT_ACF <y> <z>：原点 = PlaneMaker 作者原点 + (0, y, z)，单位米；
  2. 没有这条指令：原点 = 飞机的**默认 CG**，而 CG 在 .acf 里是明文（英尺）。
所以 作者坐标 = VEH_XYZ + 原点(米)。

实测（C90B）：_cgY 0.250 ft / _cgZ 11.450 ft → (0, 0.0762, 3.4900) m，
413 条 VEH_XYZ 换算后有 84% 落在座舱曲面 10cm 内，开关类误差 0.0–0.1cm。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

FEET = 0.3048

# .acf 是 ASCII 文本：`P acf/_cgY 0.250000000`（也有不带 P 前缀的写法）
_RE_KEY = r"^\s*(?:P\s+)?acf/%s\s+([-+0-9.eE]+)\s*$"


def _acf_value(text: str, key: str):
    m = re.search(_RE_KEY % re.escape(key), text, re.M)
    return float(m.group(1)) if m else None


def acf_default_cg(acf_path) -> tuple:
    """返回 .acf 里的默认 CG，单位米（作者坐标系）。读不到就返回 None。"""
    p = Path(acf_path)
    if not p.is_file():
        return None
    text = p.read_text(errors="ignore")
    cy, cz = _acf_value(text, "_cgY"), _acf_value(text, "_cgZ")
    if cy is None or cz is None:
        return None
    cx_l, cx_r = _acf_value(text, "_cgX_lft"), _acf_value(text, "_cgX_rgt")
    cx = 0.0 if (cx_l is None or cx_r is None) else (cx_l + cx_r) / 2.0
    return (cx * FEET, cy * FEET, cz * FEET)


def ref_point_from_doc(doc) -> tuple:
    """`.snd` 里的 REF_POINT_ACF <y> <z>（米，相对作者原点）→ 三元组。"""
    v = doc.general_value("REF_POINT_ACF")
    if not v:
        return None
    parts = [p for p in str(v).split() if p]
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return None
    if len(vals) == 0:
        return (0.0, 0.0, 0.0)
    if len(vals) == 1:
        return (0.0, vals[0], 0.0)
    return (0.0, vals[0], vals[1])


def attach_acf_path(snd_path):
    """飞机目录里找 .acf：优先同目录，其次上一级（.snd 通常在 fmod/ 下）。"""
    snd = Path(snd_path)
    for parent in (snd.parent, snd.parent.parent, snd.parent.parent.parent):
        if not parent.is_dir():
            continue
        acfs = sorted(parent.glob("*.acf"))
        if acfs:
            return acfs[0]
    return None


def resolve_origin(doc, snd_path):
    """返回 (origin_m, source, warning)。

    source: 'ref_point_acf' | 'acf_cg' | 'none'
    """
    rp = ref_point_from_doc(doc)
    if rp is not None:
        return rp, "ref_point_acf", None

    acf = attach_acf_path(snd_path)
    if acf is not None:
        cg = acf_default_cg(acf)
        if cg is not None:
            return cg, "acf_cg:%s" % os.path.basename(acf), None
        return (0.0, 0.0, 0.0), "none", "找到 %s 但没有 _cgY/_cgZ，按原点 (0,0,0) 处理" % os.path.basename(acf)

    return (0.0, 0.0, 0.0), "none", "没找到 .acf，也没 REF_POINT_ACF：坐标按原点 (0,0,0) 处理"
