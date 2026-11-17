"""生成 tests/fixtures 下的合成 .snd（不含任何 Laminar 素材，可公开提交）。

覆盖这些边角：
  * 只有 3 行头的最小文件
  * 注释框 / 分节注释 / 空行 / 结尾无换行
  * CRLF 与 LF 两种行尾
  * tab 与 4 空格混用缩进
  * 未知指令（顶层 + attachment 内）必须原样保留
  * 全部条件指令、标志位、VEH_PART / PARAM_DREF_IDX / 朝向
  * 多个 sound space（AABB + SPHERE）、REF_POINT_ACF

  python3 tests/make_fixtures.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "fixtures"
OUT.mkdir(exist_ok=True)

BOX = """#################################################
# {title}                                       #
# 0.1.0                                         #
# ci test fixture                               #
#################################################

"""

MINIMAL = "A\n1000\nACF_SOUNDS\n"

FULL = """A
1000
ACF_SOUNDS

""" + BOX.format(title="fixture full sound bank") + """
DISABLE_LEGACY_ALERT_SOUNDS
REQUIRES_BANK Master Bank
REF_POINT_ACF 1.0 -2.0

# Sound spaces
#############################################################################################
BEGIN_SOUND_SPACE
\tSOUND_INDEX 0
\tBLEND_DEPTH 0.03
\tAABB -0.800 0.100 -1.183 0.800 1.570 3.917
\tSPHERE 0.0 1.2 -1.5 0.9
END_SOUND_SPACE

BEGIN_SOUND_SPACE
\tSOUND_INDEX 1
\tSPHERE 1.0 0.5 2.0 0.4
END_SOUND_SPACE

# Snapshots
#############################################################################################

# -------------------- audio ducker ---------------------
BEGIN_SOUND_ATTACHMENT
\tSNAPSHOT_NAME /ducker
\tEVENT_START_COND sim/time/total_flight_time_sec > 0
\tEVENT_END_COND sim/time/total_flight_time_sec > 10
END_SOUND_ATTACHMENT

# -------------------- engine layers ---------------------
# 多空格分隔 + 朝向三个分量
BEGIN_SOUND_ATTACHMENT
\tEVENT_NAME /fixture/engine/turbine
\tVEH_XYZ   0.000    1.264   -0.559
\tVEH_THE 1.500
\tVEH_PSI -2.250
\tVEH_PHI 0.125
\tVEH_PART engine 0
\tPARAM_DREF_IDX 0
\tEVENT_ALWAYS
\tEVENT_ALLOWED_FOR_AI
\tEVENT_POLYPHONIC
\tEVENT_START_COND sim/flightmodel2/engines/N1_percent[0] >= 12.5
\tEVENT_END_COND sim/flightmodel2/engines/N1_percent[0] < 5
\tCUE_TRIGGER_COND sim/flightmodel2/engines/N1_percent[0] > 90
END_SOUND_ATTACHMENT

# 4 空格缩进（手写风格）
BEGIN_SOUND_ATTACHMENT
    EVENT_NAME /fixture/switches/pushbutton
    VEH_XYZ 0.296 0.798 -0.667
    EVENT_CMND_DOWN sim/fixture/push_button_down
END_SOUND_ATTACHMENT

BEGIN_SOUND_ATTACHMENT
\tEVENT_NAME /fixture/switches/hold
\tVEH_XYZ -0.447 1.034 -0.553
\tEVENT_CMND_HOLD_STOP sim/fixture/hold_stop
\tEVENT_AUTO_END_FROM_START_COND
END_SOUND_ATTACHMENT

BEGIN_SOUND_ATTACHMENT
\tEVENT_NAME /fixture/switches/hold_cue
\tVEH_XYZ 0.0 1.0 -1.0
\tEVENT_CMND_HOLD_CUE sim/fixture/hold_cue
END_SOUND_ATTACHMENT

BEGIN_SOUND_ATTACHMENT
\tEVENT_NAME /fixture/switches/up
\tVEH_XYZ 0.0 1.0 -1.0
\tVEH_THE 5.0
\tEVENT_CMND_UP sim/fixture/up
END_SOUND_ATTACHMENT

# 未知指令：必须原样保留
SOME_FUTURE_DIRECTIVE 1 2 3

BEGIN_SOUND_ATTACHMENT
\tEVENT_NAME /fixture/future/thing
\tVEH_XYZ 0.0 0.0 0.0
\tANOTHER_UNKNOWN_DIRECTIVE alpha beta
END_SOUND_ATTACHMENT

# 结尾是注释，没有空行
"""

UNKNOWN_TOP = """A
1000
ACF_SOUNDS
# 只有未知指令，没有任何 block
NEW_DIRECTIVE_WITHOUT_DOCS a b c

"""


def write(name, text, crlf=False, trailing_newline=True):
    data = text
    if not trailing_newline and data.endswith("\n"):
        data = data[:-1]
    if crlf:
        data = data.replace("\n", "\r\n")
    p = OUT / name
    p.write_bytes(data.encode("utf-8"))
    print("wrote %-28s %6d bytes%s%s" % (name, len(p.read_bytes()),
                                         " CRLF" if crlf else "",
                                         "" if trailing_newline else " (no trailing NL)"))


write("minimal.snd", MINIMAL)
write("full.snd", FULL)
write("full_crlf.snd", FULL, crlf=True)
write("no_trailing_newline.snd", MINIMAL, trailing_newline=False)
write("unknown_only.snd", UNKNOWN_TOP)
