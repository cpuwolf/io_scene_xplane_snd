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

## 轴向：默认与导入的网格对齐

Blender 是 Z-up，X-Plane 是 Y-up、Z 朝后。`io_scene_xplane_obj` / XPlane2Blender 用的变换是
（见其 `xpmesh.py` 的 `xp_to_bl`）：

```
X-Plane (x, y, z)  ->  Blender (x, -z, y)
```

导入 `.snd` 时可选两种轴向：

| 选项 | 坐标 | 用途 |
|---|---|---|
| `对齐导入网格 (XP2B)`（默认） | `(x, -z, y)` | 与 `io_scene_xplane_obj` 导入的 OBJ8 重合，可以直接叠在座舱上看 |
| `原始飞机坐标` | 原样 | 想直接对着 `.snd` 数字核对时用 |

导出时会用**导入时用的那个轴向**反算回飞机坐标，所以两种模式都能 byte-identical 往返。

实测（C90B，436 个 Speaker 对座舱 9 个 OBJ 的曲面距离）：

```
XP2B : min 0.0003  p50 0.083  p90 0.193   <=0.2m 90%     PASS
RAW  : min 2.121   p50 3.745  p90 3.940   <=0.2m  0%     FAIL（负向对照，符合预期）
```

RAW 差 3.7 米正好说明轴向映射既必要也正确 —— 不是"差一点点"，是差一个坐标轴。

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

## 为什么 custom properties 挂在 Speaker 的 Object 上，而不是 Speaker 数据块上

`.snd` 里的一条 attachment 是"**一次摆放**"（某个事件，在这架飞机的这个位置、这组条件下），
不是"一种声音"。而 Blender 的 Speaker **数据块是可以共享的**：

```python
dup = bpy.data.objects.new("copy", src.data)
dup.data == src.data          # True —— Alt+D / 手动共享数据就长这样
```

如果事件名、条件、VEH_PART 挂在 `obj.data` 上，这两个对象就共用同一组 attachment 元数据，
改一个等于改两个，导出必然打架。挂在 Object 上天然按实例独立。

其它理由：

- **位置本来就在 Object 上**（`obj.location`）。把名字/条件放 data、位置放 object，
  等于把同一条 attachment 劈成两半，用户改的时候要在两个面板之间来回跳。
- **换 Speaker 数据块不会丢元数据**（Object ▸ 数据里换别的 speaker，属性还在对象上）。
- `Object ▸ Custom Properties` 是导出器与脚本读 per-instance 元数据的惯例位置。

代价也是真的：`Shift+D` 复制出来的副本会带着同样的 `snd_uid`。所以导入时把
`uid → 对象名` 记进场景属性 `xplane_snd_owners`，导出时**按名字认领原对象**，
名字对不上的副本当**新增 attachment** 追加到文件末尾（`tests/duplicate.py` 覆盖）。

## 用法

- **把 `.snd` 直接拖进 3D 视图**（`FileHandler` 注册了 `.snd`）→ 不会弹文件对话框，直接导入
- 或者 `File > Import > X-Plane SND (.snd)` → 选飞机目录里的 `fmod/*.snd`
- 3D 视图侧栏 `X-Plane > X-Plane SND`：看原点、attachment 数、写回、Solo、全部静音
- 改完 `File > Export > X-Plane SND (.snd)` 写回（默认写回原路径）

试听：给 Speaker 的 `sound` 挂上采样文件即可。注意 Blender 的 Speaker 没有起止帧，
所有未静音的会一起播 —— 所以默认全静音，用 Solo 逐个听。

## 支持版本

定位 Blender **5.x**（`blender_version_min = "5.0.0"`），CI 只在 **5.2.4** 上验证。
4.2 / 4.5 未在 CI 里覆盖，因此 manifest 不声明支持。

## 发布流程

打一个 `v*` 的 annotated tag 并 push，CI 会：

1. 跑 lint + Blender 5.2.4 的完整测试（build / validate / install -e / smoke /
   fixtures 往返 / mutation / origin）；
2. 全绿后**自动建草稿 Release**，把 `io_scene_xplane_snd-<version>.zip` 作为附件上传；
   release 正文直接取 tag 的注释（`gh release create --notes-from-tag`）。

```bash
git tag -a v0.1.0 -m "release note..."   # 已在仓库里
git push origin main --follow-tags        # 触发 CI → 草稿 Release
```

草稿 Release 不会公开，需要你到 GitHub 上点 Publish 才算发布。
若 release job 报 403，去 Settings ▸ Actions ▸ General ▸ Workflow permissions
选 "Read and write permissions"（workflow 里已经声明 `permissions: contents: write`）。

## 无头测试

```bash
blender -b --factory-startup -P tests/roundtrip.py                 # 全盘 56 个 .snd 往返
blender -b --factory-startup -P tests/roundtrip.py -- --raw        # 用原始飞机坐标再跑一遍
blender -b --factory-startup -P tests/mutation.py                  # 新增/插入字段
blender -b --factory-startup -P tests/align_mesh.py                # 与网格对齐（自带解析器）
blender -b                  -P tests/align_mesh.py                 # 同上，但用真·io_scene_xplane_obj 导入器
blender -b                  -P tests/align_mesh.py -- --raw        # 负向对照，应该 FAIL
```

`align_mesh.py` 会优先用 `io_scene_xplane_obj` 的导入器（需要它和 XPlane2Blender 可用），
否则退回自带的 OBJ8 解析 + 同一个 `xp_to_bl` 变换，所以 CI 里不需要装任何插件。

## 现状与边界

- 只做 `.snd`：不读 bank、不碰 FMOD、不做音频编码
- 不做 `.snd` 里的触发条件编辑（条件原文保留在 custom prop 里，回写不动它）
- Sound space（`AABB`/`SPHERE`）目前只解析、不建物体（下一步）
- 几何叠加是可选的：用 `io_scene_xplane_obj` 自己导 OBJ8 进来即可，本插件不调用它

GPL-3.0-or-later
