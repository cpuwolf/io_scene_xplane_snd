# extensions.blender.org listing — io_scene_xplane_snd

商店页的元数据与正文放这里，跟版本一起更新。提交表单里的字段是**独立于 zip 内 README** 的
一份文字（审核员看到的就是这一页），改 README 不会改动它。

| 字段 | 值 |
|---|---|
| Name | `X-Plane SND Import/Export` |
| Tagline | `Edit X-Plane .snd sound attachments in 3D` |
| Tags | `Import-Export`（只这一个。加 Mesh/UV 会被按编辑网格工具审） |
| License | `SPDX:GPL-3.0-or-later` |
| Blender version | `5.2.0`（CI 覆盖 5.2.4） |
| Website | `https://github.com/cpuwolf/io_scene_xplane_snd` |
| id | `io_scene_xplane_snd`（上架后不可改） |
| Preview image | 一张 16:9（1600×900）的 3D 视图截图，见文件末尾说明 |

## Description（提交表单的正文，直接粘贴）

```markdown
Import and edit X-Plane `.snd` sound files in 3D. Every sound attachment becomes a
Speaker object placed where it will actually be heard, so you can see, move and re-export
the sound layout of an aircraft instead of editing coordinates by hand.

**What it does**

- Import `.snd` (drag the file into the 3D viewport, or File ▸ Import) — one Speaker per
  attachment, grouped by event in the Outliner.
- Speakers show the attachment's orientation (cone direction), and the sound data can be
  muted; "Solo selected" and "Mute all" make it practical to audition one cue at a time.
- Sound spaces (`AABB` / `SPHERE`) are drawn as wire volumes: the zone boundary plus an
  inner shell at `BLEND_DEPTH`, so you can see where the "inside the aircraft" mix fades
  out. Move or scale the boundary and it is written back as the new `AABB` / sphere;
  `BLEND_DEPTH` is editable through the object's custom properties.
- Move or duplicate Speakers in the viewport, rename whole events, then export.
- Export patches the original file: lines you did not touch are written back byte for byte
  (same tabs, comments, line order and line endings). Files from other tools survive the
  round trip unchanged.
- Axes match the OBJ8 importers ((x, y, z) → (x, -z, y)), so the Speakers line up with the
  cockpit geometry you already imported. A raw aircraft-coordinate mode is also available.

**Files it reads and writes**

- Reads the `.snd` file you pick, plus the aircraft's `.acf` file in the same or a nearby
  folder (the sound coordinates are relative to an origin stored there: `REF_POINT_ACF`, or
  the aircraft's default CG).
- Writes only the `.snd` file you choose on export.
- No network access, no background processes, no other add-on required.

**Requirements**

- Blender 5.2 or newer.
- An X-Plane aircraft `.snd` file (`ACF_SOUNDS`), as used by X-Plane 12.

**Not included**

- FMOD banks and event definitions are not read or modified; only the `.snd` layout is.
- Trigger conditions are preserved and can be copied to new attachments, but there is no
  condition editor.
- Sound spaces (`AABB` / `SPHERE`) are parsed and kept, but not drawn as geometry yet.

Source and issue tracker: https://github.com/cpuwolf/io_scene_xplane_snd
```

## What's New（上传新版本时填）

首版，无。

## Icon（提交表单的图标字段）

| 文件 | 底色 | 用在哪 |
|---|---|---|
| `branding/icon_light_256.png` | `#EEF0F3` | 商店列表页（页面底 `#25282D`，浅底才跳得出来） |
| `branding/icon_dark_256.png` | `#16191D` | README / GitHub / 浅色背景的文档 |

- 256×256 PNG，圆角 46/256 已经画进文件（平台只再加 3 px）；展示尺寸是详情页 32、
  作者页 48，所以**按 32 px 验收**：扬声器锥 + 两道弧的剪影在 32 px 下仍认得出。
- 只有几何图形，没有文字、没有 Blender logo、没有真机外形。
- `branding/make_icon.py` 生成两份 SVG 源；PNG 由无头 Chrome 按 256 渲染（本机没有
  svg→png 转换器）。换色改脚本里的颜色常量即可。
- `/branding/` 在 manifest 的 `paths_exclude_pattern` 里，不会进安装包。

## Preview image（详情页大图）

- 一张 16:9、1600×900 的截图；平台自己生成 640×360 卡片和 1920×1080 大图。
- 内容：导入后的 3D 视图（Speaker 锥体落在座舱里）+ Outliner 里 `SND <file> / <event>`
  的 collection，再加侧栏面板。能让审核员和用户一眼看出“导入了什么、放在哪”。
- 不要在图上放 Blender logo/图标，也不要写大段说明文字。
