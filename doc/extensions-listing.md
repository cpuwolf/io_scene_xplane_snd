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

## Preview image

- 一张 16:9、1600×900 的截图；平台自己生成 640×360 卡片和 1920×1080 大图。
- 内容：导入后的 3D 视图（Speaker 锥体落在座舱里）+ Outliner 里 `SND <file> / <event>`
  的 collection，再加侧栏面板。能让审核员和用户一眼看出“导入了什么、放在哪”。
- 不要在图上放 Blender logo/图标，也不要写大段说明文字。
