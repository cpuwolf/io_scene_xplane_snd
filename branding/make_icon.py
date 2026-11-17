"""生成 io_scene_xplane_snd 的扩展图标 SVG（256×256 画布，两版底色）。

画法按 store-listing-assets 的实测规则：
  * 圆角 46/256（≈18%）画进文件，平台只再叠 3 px；
  * 单一剪影（扬声器锥 + 两道声波弧），文字零、无 Blender logo、无真机外形；
  * 弧线宽 12/256，两道弧间距在 32 px 下仍能分开（半径 34 / 68，同心在锥尖）；
  * 图形按 bbox 居中、放大 1.22 倍，四周留 ≈15% 安全边。

本机没有 svg→png 转换器（rsvg-convert / magick / cairosvg 都没有），PNG 用一个
viewBox 与目标一致的 HTML 方块 + 无头 Chrome 精确截图得到，见 README 的“图标”段。

  python3 branding/make_icon.py     # 只写 SVG 源
"""
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

LIGHT_BG, INK = "#EEF0F3", "#1B1E23"     # 浅底版：给深色列表页（#25282D）
DARK_BG, AMBER = "#16191D", "#F2A33C"   # 深底版：给浅色背景（README / GitHub）

CX, CY = 139.0, 128.0        # 弧心 = 扬声器锥尖
RADII = (34.0, 68.0)
STROKE = 12.0
SCALE = 1.22


def arc(r, a=50.0):
    rad = math.radians(a)
    x, y = CX + r * math.cos(rad), CY
    return (f'M {x:.2f} {y - r * math.sin(rad):.2f} '
            f'A {r:.2f} {r:.2f} 0 0 0 {x:.2f} {y + r * math.sin(rad):.2f}')


def svg(bg, fg):
    arcs = "".join(f'<path d="{arc(r)}"/>' for r in RADII)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect width="256" height="256" rx="46" fill="{bg}"/>
  <g transform="translate(128 128) scale({SCALE}) translate(-128 -128)">
    <g fill="{fg}">
      <rect x="55" y="100" width="20" height="56" rx="6"/>
      <polygon points="75,100 139,74 139,182 75,156"/>
    </g>
    <g fill="none" stroke="{fg}" stroke-width="{STROKE}" stroke-linecap="round">{arcs}</g>
  </g>
</svg>
'''


if __name__ == "__main__":
    (HERE / "icon_light.svg").write_text(svg(LIGHT_BG, INK))
    (HERE / "icon_dark.svg").write_text(svg(DARK_BG, AMBER))
    print(HERE / "icon_light.svg")
    print(HERE / "icon_dark.svg")
