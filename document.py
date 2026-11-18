"""X-Plane .snd 的"保留原文"模型。

设计原则（这是整个插件的地基）：
  * 读进来时记住**每一行的原文**，导出时只重写真正改过的行；
  * 没改过的文件，导出结果必须与输入 **逐字节相同**（含 tab 缩进、注释、空行顺序、换行符）；
  * 不认识的指令、注释、乱序行，一律原样留着，不重排、不"美化"。

所以 Document 内部是一组 raw lines + 解析出的 attachment 索引，
写回时可以做到"patch 而不是 regenerate"。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

HEADER = ("A", "1000", "ACF_SOUNDS")

ATTACH_FIELDS = {
    "EVENT_NAME", "SNAPSHOT_NAME", "VEH_XYZ", "VEH_THE", "VEH_PSI", "VEH_PHI",
    "VEH_PART", "PARAM_DREF_IDX", "EVENT_ALLOWED_FOR_AI", "EVENT_ALWAYS",
    "EVENT_POLYPHONIC", "EVENT_AUTO_END_FROM_START_COND",
    "EVENT_START_COND", "EVENT_END_COND", "CUE_TRIGGER_COND",
    "EVENT_CMND_DOWN", "EVENT_CMND_UP", "EVENT_CMND_HOLD_STOP", "EVENT_CMND_HOLD_CUE",
}
SPACE_FIELDS = {"SOUND_INDEX", "BLEND_DEPTH", "AABB", "SPHERE"}
COND_FIELDS = {"EVENT_START_COND", "EVENT_END_COND", "CUE_TRIGGER_COND",
               "EVENT_CMND_DOWN", "EVENT_CMND_UP", "EVENT_CMND_HOLD_STOP",
               "EVENT_CMND_HOLD_CUE"}

RE_KV = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Z][A-Z0-9_]*)(?:\s+(?P<rest>.*?))?\s*$")


@dataclass
class LineField:
    """一行指令：原文 + 拆出来的 key/值。"""
    line_no: int
    raw: str
    key: str
    rest: str
    indent: str


@dataclass
class Attachment:
    index: int
    begin_line: int
    end_line: int = -1
    kind: str = "event"                    # event | snapshot
    name: Optional[str] = None
    xyz: Optional[tuple] = None
    the: Optional[float] = None
    psi: Optional[float] = None
    phi: Optional[float] = None
    part: Optional[tuple] = None           # (part_name, index)
    dref_idx: Optional[int] = None
    flags: list = field(default_factory=list)
    conds: list = field(default_factory=list)      # [(key, value)] 保持顺序
    fields: list = field(default_factory=list)     # [LineField]
    remark: Optional[str] = None                   # 紧邻上方的注释行（只读展示）

    def field_lines(self, key):
        return [f for f in self.fields if f.key == key]

    def one(self, key):
        fl = self.field_lines(key)
        return fl[0].rest if fl else None


@dataclass
class SpaceVolume:
    """sound space 里的一个体积（AABB 或 SPHERE），带行号以便原地 patch。"""
    kind: str                                     # "AABB" | "SPHERE"
    line_no: int
    values: tuple                                 # AABB: 6 个数 / SPHERE: (x, y, z, r)，米，相对 CG
    indent: str = "\t"

    def text(self) -> str:
        return "%s%s %s" % (self.indent, self.kind,
                            " ".join("%.3f" % float(v) for v in self.values))


@dataclass
class SoundSpace:
    index: int
    begin_line: int
    end_line: int = -1
    remark: Optional[str] = None                   # 紧邻上方的注释（通常是区域名：Cockpit / Passenger cabin）
    sound_index: Optional[int] = None               # → sim/operation/sound/inside_ratio[n]
    sound_line: Optional[int] = None                # SOUND_INDEX 所在行（插入 BLEND_DEPTH 时的锚点）
    blend_depth: Optional[float] = None             # 从边界向内 m 米的软过渡
    blend_line: Optional[int] = None                # BLEND_DEPTH 所在行（没有则为 None）
    volumes: list = field(default_factory=list)     # [SpaceVolume, ...]，同一 space 内多个体积取并集

    @property
    def aabbs(self):
        return [v.values for v in self.volumes if v.kind == "AABB"]

    @property
    def spheres(self):
        return [v.values for v in self.volumes if v.kind == "SPHERE"]


class Document:
    """一个 .snd 文件的内存表示。raw lines 是唯一真相，解析结果只是索引。"""

    def __init__(self, text: str):
        self.text_in = text
        self.lines = text.splitlines(keepends=True)
        self.eol = "\r\n" if (self.lines and self.lines[0].endswith("\r\n")) else "\n"
        self.header_ok = False
        self.general = []            # [(key, rest, line_no)]
        self.attachments: list[Attachment] = []
        self.spaces: list[SoundSpace] = []
        self.warnings: list[str] = []
        self._parse()

    # ---------------- 解析 ----------------
    def _parse(self):
        lines = self.lines
        i = 0
        n = len(lines)
        # 头部三行（允许前面有 BOM/空行）
        head = []
        while i < n and len(head) < 3:
            s = lines[i].strip().lstrip("\ufeff")
            if s == "":
                i += 1
                continue
            head.append(s)
            i += 1
        self.header_ok = tuple(head[:3]) == HEADER
        if not self.header_ok:
            self.warnings.append("头部不是 A / 1000 / ACF_SOUNDS：%r" % (head[:3],))

        cur_att = None
        cur_spa = None
        last_comment = None
        while i < n:
            raw = lines[i]
            s = raw.strip()
            if not s:
                i += 1
                continue
            if s.startswith("#"):
                last_comment = s.lstrip("#").strip()
                i += 1
                continue
            m = RE_KV.match(raw)
            if not m:
                self.warnings.append("第 %d 行无法识别，原样保留: %r" % (i + 1, s[:60]))
                i += 1
                continue
            key, rest, indent = m.group("key"), (m.group("rest") or ""), m.group("indent")

            if key == "BEGIN_SOUND_ATTACHMENT":
                cur_att = Attachment(index=len(self.attachments), begin_line=i, remark=last_comment)
                self.attachments.append(cur_att)
                last_comment = None
            elif key == "END_SOUND_ATTACHMENT":
                if cur_att is None:
                    self.warnings.append("第 %d 行 END_SOUND_ATTACHMENT 没有配对" % (i + 1))
                else:
                    cur_att.end_line = i
                    cur_att = None
                last_comment = None
            elif key == "BEGIN_SOUND_SPACE":
                cur_spa = SoundSpace(index=len(self.spaces), begin_line=i,
                                     remark=_clean_remark(last_comment))
                self.spaces.append(cur_spa)
                last_comment = None
            elif key == "END_SOUND_SPACE":
                if cur_spa is not None:
                    cur_spa.end_line = i
                    cur_spa = None
                last_comment = None
            elif cur_att is not None:
                self._attach_field(cur_att, key, rest, i, raw, indent)
            elif cur_spa is not None:
                if key == "SOUND_INDEX":
                    cur_spa.sound_index = _int(rest)
                    cur_spa.sound_line = i
                elif key == "BLEND_DEPTH":
                    cur_spa.blend_depth = _float(rest)
                    cur_spa.blend_line = i
                elif key in ("AABB", "SPHERE"):
                    want = 6 if key == "AABB" else 4
                    vals = _floats(rest, want)
                    if vals is None:
                        self.warnings.append(
                            "第 %d 行 %s 数值不足（要 %d 个），已忽略这个体积: %r"
                            % (i + 1, key, want, rest[:40]))
                    else:
                        cur_spa.volumes.append(SpaceVolume(kind=key, line_no=i,
                                                           values=tuple(vals), indent=indent))
            else:
                self.general.append((key, rest, i))
            i += 1

        if cur_att is not None:
            self.warnings.append("文件结束时仍有未闭合的 BEGIN_SOUND_ATTACHMENT")

    def _attach_field(self, att: Attachment, key: str, rest: str, i: int, raw: str, indent: str):
        att.fields.append(LineField(line_no=i, raw=raw, key=key, rest=rest, indent=indent))
        if key == "EVENT_NAME":
            att.kind, att.name = "event", rest
        elif key == "SNAPSHOT_NAME":
            att.kind, att.name = "snapshot", rest
        elif key == "VEH_XYZ":
            v = _floats(rest, 3)
            att.xyz = tuple(v) if v else None
        elif key == "VEH_THE":
            att.the = _float(rest)
        elif key == "VEH_PSI":
            att.psi = _float(rest)
        elif key == "VEH_PHI":
            att.phi = _float(rest)
        elif key == "VEH_PART":
            p = rest.split()
            if len(p) >= 2:
                att.part = (p[0], _int(p[1]))
        elif key == "PARAM_DREF_IDX":
            att.dref_idx = _int(rest)
        elif key in ("EVENT_ALLOWED_FOR_AI", "EVENT_ALWAYS", "EVENT_POLYPHONIC",
                     "EVENT_AUTO_END_FROM_START_COND"):
            att.flags.append(key)
        elif key in COND_FIELDS:
            att.conds.append((key, rest))

    # ---------------- 通用指令 ----------------
    def general_value(self, key):
        for k, rest, _ in self.general:
            if k == key:
                return rest
        return None

    # ---------------- 写回 ----------------
    def to_text(self) -> str:
        return "".join(self.lines)

    def render(self) -> str:
        """按当前 lines 输出（改过的行已经被 patch 进去了）。"""
        return "".join(self.lines)

    def set_line(self, line_no: int, new_raw: str):
        """替换一行，保持该行原本的换行符。"""
        old = self.lines[line_no]
        eol = "\r\n" if old.endswith("\r\n") else ("\n" if old.endswith("\n") else "")
        self.lines[line_no] = new_raw.rstrip("\r\n") + eol

    def patch_attachment(self, att: Attachment, *, name=None, xyz=None, the=None, psi=None, phi=None):
        """只改这次真正变了的字段；每一处都沿用原来的缩进。"""
        changed = []
        if name is not None and att.name is not None and str(name) != att.name:
            key = "SNAPSHOT_NAME" if att.kind == "snapshot" else "EVENT_NAME"
            fls = att.field_lines(key)
            if fls:
                fl = fls[0]
                new_name = str(name)
                self.set_line(fl.line_no, "%s%s %s" % (fl.indent, key, new_name))
                fl.rest = new_name
                att.name = new_name
                changed.append(key)
        if xyz is not None and att.xyz is not None:
            newv = tuple(round(float(v), 3) for v in xyz)
            if newv != tuple(att.xyz):
                fl = att.field_lines("VEH_XYZ")[0]
                self.set_line(fl.line_no, "%sVEH_XYZ %.3f %.3f %.3f" % ((fl.indent,) + newv))
                att.xyz = newv
                changed.append("VEH_XYZ")
        for key, cur, new in (("VEH_THE", att.the, the), ("VEH_PSI", att.psi, psi), ("VEH_PHI", att.phi, phi)):
            if new is None:
                continue
            if cur is None:
                # 原本没有这个字段：加在 VEH_XYZ 之后
                anchor = att.field_lines("VEH_XYZ") or att.field_lines("EVENT_NAME") or att.field_lines("SNAPSHOT_NAME")
                if not anchor:
                    continue
                indent = anchor[0].indent
                ins = anchor[0].line_no + 1
                self.lines.insert(ins, "%s%s %.3f%s" % (indent, key, float(new), self.eol))
                self._shift_after(ins, +1, skip=att)
                att.fields.append(LineField(line_no=ins, raw=self.lines[ins], key=key,
                                            rest="%.3f" % float(new), indent=indent))
                setattr(att, {"VEH_THE": "the", "VEH_PSI": "psi", "VEH_PHI": "phi"}[key], float(new))
                changed.append(key)
            else:
                newf = round(float(new), 3)
                if abs(newf - float(cur)) > 1e-9:
                    fl = att.field_lines(key)[0]
                    self.set_line(fl.line_no, "%s%s %.3f" % (fl.indent, key, newf))
                    setattr(att, {"VEH_THE": "the", "VEH_PSI": "psi", "VEH_PHI": "phi"}[key], newf)
                    changed.append(key)
        return changed

    def _indent_of(self, line_no: int) -> str:
        m = RE_KV.match(self.lines[line_no])
        return m.group("indent") if m else "\t"

    def patch_space_volume(self, space, volume_index: int, values) -> bool:
        """把一个 AABB/SPHERE 的数值改掉（只重写那一行，保留缩进）。返回是否真的改了。"""
        if not (0 <= volume_index < len(space.volumes)):
            return False
        vol = space.volumes[volume_index]
        new = tuple(round(float(v), 3) for v in values)
        if len(new) != len(vol.values):
            return False
        if tuple(round(float(v), 3) for v in vol.values) == new:
            return False
        self.set_line(vol.line_no, "%s%s %s" % (vol.indent, vol.kind,
                                                " ".join("%.3f" % v for v in new)))
        vol.values = new
        return True

    def patch_space_blend(self, space, value) -> bool:
        """改 BLEND_DEPTH；原本没有这一行就插在 SOUND_INDEX 之后。"""
        new = round(float(value), 3)
        if new < 0:
            return False
        if space.blend_depth is not None and abs(float(space.blend_depth) - new) < 5e-4:
            return False
        if space.blend_line is not None:
            self.set_line(space.blend_line,
                          "%sBLEND_DEPTH %.3f" % (self._indent_of(space.blend_line), new))
        else:
            anchor = space.sound_line if space.sound_line is not None else space.begin_line
            ins = anchor + 1
            self.lines.insert(ins, "%sBLEND_DEPTH %.3f%s" % (self._indent_of(anchor), new, self.eol))
            self._shift_after(ins, +1)
            space.blend_line = ins
        space.blend_depth = new
        return True

    def _shift_after(self, line_no: int, delta: int, skip: Attachment = None):
        """插入/删除行后，修正后面所有对象的行号索引。"""
        for a in self.attachments:
            if a is skip:
                continue
            if a.begin_line > line_no:
                a.begin_line += delta
            if a.end_line >= line_no:
                a.end_line += delta
            for f in a.fields:
                if f.line_no >= line_no:
                    f.line_no += delta
        for s in self.spaces:
            if s.begin_line > line_no:
                s.begin_line += delta
            if s.end_line >= line_no:
                s.end_line += delta
            for attr in ("sound_line", "blend_line"):
                cur = getattr(s, attr)
                if cur is not None and cur >= line_no:
                    setattr(s, attr, cur + delta)
            for v in s.volumes:
                if v.line_no >= line_no:
                    v.line_no += delta
        self.general = [(k, r, (ln + delta if ln >= line_no else ln)) for k, r, ln in self.general]

    def reparse(self):
        """按当前 lines 重新解析（插入新的 space/体积块之后调用，让索引重新对齐）。"""
        self.__init__("".join(self.lines))

    def _space_insert_anchor(self) -> int:
        """新 space 该插在哪：最后一个 END_SOUND_SPACE 之后（Laminar 的排版也是 space 在前）。"""
        ends = [s.end_line for s in self.spaces if s.end_line >= 0]
        if ends:
            return max(ends) + 1
        # 没有 space：插在头部三行之后（跳过 BOM/空行）
        i = 0
        head = 0
        while i < len(self.lines) and head < 3:
            if self.lines[i].strip().lstrip("\ufeff"):
                head += 1
            i += 1
        return i

    def insert_volume(self, space, kind: str, values, indent=None) -> None:
        """在 END_SOUND_SPACE 之前插一行 AABB/SPHERE（往已有分区里加体积）。"""
        indent = indent or (space.volumes[0].indent if space.volumes else "\t")
        at = space.end_line if space.end_line >= 0 else len(self.lines) - 1
        line = "%s%s %s%s" % (indent, kind, " ".join("%.3f" % float(v) for v in values), self.eol)
        self.lines.insert(at, line)
        self._shift_after(at, +1)
        self.reparse()

    def insert_space(self, sound_index: int, blend_depth=None, volumes=(), remark=None) -> None:
        """追加一个 BEGIN_SOUND_SPACE … END_SOUND_SPACE 块。

        volumes: [(kind, values), ...]；一个 space 可以有多个体积（规范里是并集）。
        """
        block = []
        if remark:
            block.append("# -------------------- %s ---------------------%s" % (remark, self.eol))
        block.append("BEGIN_SOUND_SPACE%s" % self.eol)
        block.append("\tSOUND_INDEX %d%s" % (int(sound_index), self.eol))
        if blend_depth is not None:
            block.append("\tBLEND_DEPTH %.3f%s" % (float(blend_depth), self.eol))
        for kind, vals in volumes:
            block.append("\t%s %s%s" % (kind, " ".join("%.3f" % float(v) for v in vals), self.eol))
        block.append("END_SOUND_SPACE%s" % self.eol)

        at = self._space_insert_anchor()
        if at > 0 and self.lines[at - 1].strip() and not block[0].startswith("#"):
            block.insert(0, self.eol)          # 与前一个块之间留一个空行
        self.lines[at:at] = block
        self._shift_after(at, +len(block))
        self.reparse()

    def append_attachment(self, *, kind, name, xyz, indent="\t", remark=None,
                          the=None, psi=None, phi=None, part=None, dref_idx=None,
                          flags=None, conds=None):
        """在文件末尾追加一个 attachment（新做的音源）。

        字段顺序对齐 x-snd-lib 的输出：名字 → 位置 → 朝向 → 零件 → 索引 → 标志 → 条件。
        """
        block = []
        if remark:
            block.append("# -------------------- %s ---------------------%s" % (remark, self.eol))
        block.append("BEGIN_SOUND_ATTACHMENT%s" % self.eol)
        block.append("%s%s %s%s" % (indent, "EVENT_NAME" if kind == "event" else "SNAPSHOT_NAME", name, self.eol))
        block.append("%sVEH_XYZ %.3f %.3f %.3f%s" % ((indent,) + tuple(round(float(v), 3) for v in xyz) + (self.eol,)))
        for key, val in (("VEH_THE", the), ("VEH_PSI", psi), ("VEH_PHI", phi)):
            if val is not None:
                block.append("%s%s %.3f%s" % (indent, key, float(val), self.eol))
        if part:
            block.append("%sVEH_PART %s %d%s" % (indent, part[0], int(part[1]), self.eol))
        if dref_idx is not None:
            block.append("%sPARAM_DREF_IDX %d%s" % (indent, int(dref_idx), self.eol))
        for f in (flags or []):
            block.append("%s%s%s" % (indent, f, self.eol))
        for k, v in (conds or []):
            block.append("%s%s %s%s" % (indent, k, v, self.eol))
        block.append("END_SOUND_ATTACHMENT%s" % self.eol)
        if self.lines and not self.lines[-1].endswith("\n"):
            self.lines[-1] += self.eol
        self.lines.extend(block)
        att = Attachment(index=len(self.attachments), begin_line=len(self.lines) - len(block),
                         end_line=len(self.lines) - 1, kind=kind, name=name,
                         xyz=tuple(round(float(v), 3) for v in xyz), remark=remark)
        base_line = len(self.lines) - len(block)
        for offset, line in enumerate(block):
            ln = base_line + offset
            m = RE_KV.match(line)
            if not m:
                continue
            att.fields.append(LineField(line_no=ln, raw=line, key=m.group("key"),
                                        rest=(m.group("rest") or ""), indent=m.group("indent")))
        att.the, att.psi, att.phi = the, psi, phi
        att.part = tuple(part) if part else None
        att.dref_idx = dref_idx
        att.flags = list(flags or [])
        att.conds = list(conds or [])
        self.attachments.append(att)
        return att


def _float(s, default=None):
    try:
        return float(str(s).split()[0])
    except Exception:
        return default


def _int(s, default=None):
    try:
        return int(str(s).split()[0])
    except Exception:
        return default


def _floats(s, count):
    try:
        v = [float(x) for x in str(s).split()[:count]]
        return v if len(v) == count else None
    except Exception:
        return None


def _clean_remark(text):
    """注释横幅（`# -------------------- Cockpit ----------`）→ 只留区域名。"""
    if not text:
        return None
    s = str(text).strip().strip("#").strip()
    s = re.sub(r"^[-=\s]+|[-=\s]+$", "", s)
    return s or None


def read_file(path) -> Document:
    # newline='' 保留原始换行符，这是 byte-identical 往返的前提
    with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        return Document(fh.read())


def write_file(path, doc: Document):
    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        fh.write(doc.render())
