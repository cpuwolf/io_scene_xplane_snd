# io_scene_xplane_snd

Blender 里编辑 X-Plane 的 `.snd` 文件：每个 sound attachment 变成场景里的一个 **Speaker**，
在三维里看位置、拖动摆位，再写回 `.snd`。

**零依赖**：不需要 XPlane2Blender，也不需要 `io_scene_xplane_obj`，只用 Blender 自带 API +
Python 标准库。因此 `blender -b` 下可以完整跑回归测试。

## 为什么用 Speaker 而不是 Empty

| Speaker 提供 | 用途 |
|---|---|
| 物体 location | 对应 `VEH_XYZ`（自动加 CG 偏移） |
| 锥体 + 旋转 | 对应 `VEH_THE / PSI / PHI`，能看出"朝哪边" |
| `sound` 数据块 | 挂上重建工程里的 `Assets/*.ogg` 就能试听（Blender 直接读我们 mux 出来的 ogg：48k/立体声） |
| `muted` | 默认全静音，用「Solo 选中」单独听 |

Speaker 自己的衰减/音量字段**写不回** `.snd`（这些由 FMOD 事件管），所以数据仍然以
custom properties 为准：`snd_event` / `snd_conds` / `snd_part` / `snd_xyz` / `snd_line`。

## 坐标

`.snd` 的 `VEH_XYZ` 是"相对原点"的米制坐标，原点按这个顺序确定：

1. 文件里有 `REF_POINT_ACF <y> <z>` → 原点 = 作者原点 + (0, y, z)；
2. 否则读飞机 `.acf` 的默认 CG（`acf/_cgY`、`acf/_cgZ`，单位英尺→米）；
3. 都没有 → 原点 (0,0,0) 并给出警告。

所以 `作者坐标 = VEH_XYZ + 原点`。C90B 实测：413 条 `VEH_XYZ` 换算后 **84%** 落在座舱曲面
10 cm 内，开关类误差 **0.0–0.1 cm**，最远的 `fuel_pump ±1.948 m` 正好是机翼位置。

## 导出：保留原文，只 patch 改动行

`.snd` 里有大量注释和空行（C90B：2993 行里 288 行注释 + 272 行空行），全量重写会把它们
和作者的排版一起毁掉。所以导出是**行级 patch**：

- 没改过的行原样输出 → 未修改的文件写回后与输入**逐字节相同**
- 改坐标只重写那条 `VEH_XYZ` 的数字，tab 缩进和行序不动
- 新增的 Speaker 追加到文件末尾

实测：X-Plane 12 安装目录下 **56 个 `.snd`（含 payware、场景车辆、jetway、航母）全部 byte-identical**；
移动一个 Speaker 后 diff 恰好 **1 行**：

```
L148  - \tVEH_XYZ 0.000 1.264 -0.559
L148  + \tVEH_XYZ 0.000 1.364 -0.559
```

## 用法

- `File > Import > X-Plane SND (.snd)` → 选飞机目录里的 `fmod/*.snd`
- 3D 视图侧栏 `X-Plane > X-Plane SND`：看原点、attachment 数、写回、Solo、全部静音
- 改完 `File > Export > X-Plane SND (.snd)` 写回（默认写回原路径）

试听：给 Speaker 的 `sound` 挂上采样文件即可。注意 Blender 的 Speaker 没有起止帧，
所有未静音的会一起播 —— 所以默认全静音，用 Solo 逐个听。

## 无头测试

```bash
blender -b --factory-startup -P tests/roundtrip.py                 # 扫全盘 .snd
blender -b --factory-startup -P tests/roundtrip.py -- <某个.snd>    # 只测一个
```

## 现状与边界

- 只做 `.snd`：不读 bank、不碰 FMOD、不做音频编码
- 不做 `.snd` 里的触发条件编辑（条件原文保留在 custom prop 里，回写不动它）
- Sound space（`AABB`/`SPHERE`）目前只解析、不建物体（下一步）
- 几何叠加是可选的：用 `io_scene_xplane_obj` 自己导 OBJ8 进来即可，本插件不调用它

GPL-3.0-or-later
