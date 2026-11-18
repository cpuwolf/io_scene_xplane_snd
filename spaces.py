"""把 .snd 的 sound space（AABB / SPHERE）在 Blender 里画出来，并把改动写回。

.snd 里一个 sound space 决定 `sim/operation/sound/inside_ratio[n]` 这个 0..1 的听感系数：
点在体积内 = 1（车内声），体积外 = 0（车外声），边界向内 BLEND_DEPTH 米是线性软过渡。

所以可视化分两层，而不是只画一个盒子：

  boundary 外框 = 体积的数学边界（AABB 的 6 个数 / SPHERE 的球面）
  core   内框 = 边界向内缩 BLEND_DEPTH 米 —— 两个框之间的带子就是软过渡区

画法上的选择（都是为了"在座舱网格里也看得见"，而不是好看）：

  * 实体面 + Wireframe 修改器 → 边缘变成有厚度的管子，**任何着色模式都有颜色**；
    纯线框对象在 Solid 模式下用的是主题线色（灰），贴在座舱里基本看不见。
  * `show_in_front = True`：透过机身/座舱网格看到这个框。
  * 每个对象一个视口显示色（Workbench 的 Material 颜色模式读 `material.diffuse_color`），
    AABB 琥珀、SPHERE 青，core 用同色系压暗 —— 一眼分得清边界和过渡区。

编辑面（写回细节见 sync() 的 docstring）：

  * 拖 / 缩放 / 旋转 boundary 框 → AABB 的 6 个数按转完后的世界包围盒重算；
  * 拖 / 缩放球 → SPHERE 的球心与半径；
  * 改对象的 `snd_blend_depth` 自定义属性 → BLEND_DEPTH 那一行（原本没有就插一行）；
  * core 框是派生物，动它不写回 —— 它只是把 BLEND_DEPTH 画出来。
"""
from __future__ import annotations

import bmesh
import bpy

from . import acftool

KIND_AABB = "AABB"
KIND_SPHERE = "SPHERE"

# (边界色, core 色) —— core 是同色压暗，避免"两种颜色代表两种含义"的误读
PALETTE = {
    KIND_AABB: ((0.95, 0.64, 0.24, 1.0), (0.52, 0.34, 0.12, 1.0)),
    KIND_SPHERE: ((0.31, 0.76, 0.97, 1.0), (0.16, 0.40, 0.52, 1.0)),
}
ROLE_BOUNDARY = "boundary"
ROLE_CORE = "core"

SPHERE_SEGMENTS, SPHERE_RINGS = 24, 12
TOL = 5e-4          # 0.5 mm：小于它当作"没动过"，保证未编辑的文件导出仍逐字节相同


def _material(kind, role):
    """一个 (kind, role) 一份材质：视口色 + 自发光，Solid/Material/Render 都有颜色。"""
    name = "SND %s %s" % (kind, role)
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    color = PALETTE.get(kind, PALETTE[KIND_AABB])[0 if role == ROLE_BOUNDARY else 1]
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color                      # Workbench 的 Material 颜色模式读这个
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        # 4.x 起是 "Emission Color"，旧版是 "Emission"：两个名字都试一次
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = color
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = 2.0
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color
    return mat


def _finish(obj, coll, kind, role, mat, thickness):
    """统一后处理：材质 + Wireframe 管 + 透视可见。"""
    obj.data.materials.append(mat)
    mod = obj.modifiers.new("Wire", "WIREFRAME")
    mod.thickness = thickness
    mod.use_replace = True
    mod.use_even_offset = False
    obj.show_in_front = True                       # 座舱网格里也看得见
    obj.display_type = "SOLID"
    coll.objects.link(obj)
    return obj


def _box_obj(name, aabb, origin, axis, coll, kind, role, mat, thickness):
    """AABB(minx,miny,minz,maxx,maxy,maxz) → 立方体网格；坐标 = 飞机坐标 + 原点，再按轴向模式转。

    网格顶点是**相对盒子中心**的，对象放在中心上 —— 这样 S/R 的枢轴就是盒子中心，
    而不是模型原点（否则一缩放盒子就会朝飞机原点方向飘走）。
    """
    mn, mx = aabb[:3], aabb[3:]
    xs = (mn[0], mx[0]); ys = (mn[1], mx[1]); zs = (mn[2], mx[2])
    corners = [(x, y, z) for x in xs for y in ys for z in zs]
    world = [acftool.to_blender((c[0] + origin[0], c[1] + origin[1], c[2] + origin[2]), axis)
             for c in corners]
    center = tuple(sum(p[i] for p in world) / 8.0 for i in range(3))
    verts = [tuple(p[i] - center[i] for i in range(3)) for p in world]
    # corners 顺序是 (x, y, z) 的二进制计数：0=(000) … 7=(111)
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = center
    return _finish(obj, coll, kind, role, mat, thickness)


def _sphere_obj(name, sphere, origin, axis, coll, kind, role, mat, thickness):
    x, y, z, r = sphere
    bm = bmesh.new()
    try:
        bmesh.ops.create_uvsphere(bm, u_segments=SPHERE_SEGMENTS, v_segments=SPHERE_RINGS, radius=r)
    except TypeError:                       # 老版本参数名是 diameter
        bmesh.ops.create_uvsphere(bm, u_segments=SPHERE_SEGMENTS, v_segments=SPHERE_RINGS,
                                  diameter=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = acftool.to_blender(
        (x + origin[0], y + origin[1], z + origin[2]), axis)
    return _finish(obj, coll, kind, role, mat, thickness)


def _inset(aabb, depth):
    """边界向内缩 depth 米；任意一维缩没了就不画 core（返回 None）。"""
    mn = [aabb[i] + depth for i in range(3)]
    mx = [aabb[i + 3] - depth for i in range(3)]
    if any(mx[i] <= mn[i] for i in range(3)):
        return None
    return tuple(mn + mx)


def _tube(size):
    """线框管的粗细按体积尺寸的 0.5% 给：不管 3 m 的座舱还是 30 m 的客舱，屏幕上是同一个视觉重量。"""
    return max(0.008, min(0.2, size * 0.005))


def _tag(obj, space, kind, role, volume_index):
    obj["snd_space_index"] = int(space.index)
    obj["snd_volume_index"] = int(volume_index)
    obj["snd_space_kind"] = kind
    obj["snd_space_role"] = role
    if space.sound_index is not None:
        obj["snd_sound_index"] = int(space.sound_index)
    if space.blend_depth is not None:
        obj["snd_blend_depth"] = float(space.blend_depth)
    obj["snd_space_line"] = int(space.begin_line) + 1
    if space.remark:
        obj["snd_space_area"] = space.remark
    # 导入时的对象名：Shift+D 出来的副本名字会变，据此认出"谁是原对象"
    obj["snd_owner_name"] = obj.name


def build(scene, doc, origin, axis, parent_coll):
    """为一个 .snd 的所有 sound space 建可视化对象，返回 (collection, 对象数)。"""
    if not doc.spaces:
        return None, 0
    name = "Sound spaces"
    coll = bpy.data.collections.get(parent_coll.name + " / " + name)
    if coll is None:
        coll = bpy.data.collections.new(parent_coll.name + " / " + name)
        parent_coll.children.link(coll)

    made = 0
    for space in doc.spaces:
        depth = float(space.blend_depth or 0.0)
        area = (space.remark or "").strip()
        for vi, vol in enumerate(space.volumes):
            label = "SPACE_%02d_%s" % (space.index, area or vol.kind)
            if len(space.volumes) > 1:
                label += "_v%d" % vi
            if vol.kind == KIND_AABB:
                aabb = vol.values
                size = max(max(aabb[i + 3] - aabb[i] for i in range(3)), 0.05)
                th = _tube(size)
                obj = _box_obj(label, aabb, origin, axis, coll, KIND_AABB, ROLE_BOUNDARY,
                               _material(KIND_AABB, ROLE_BOUNDARY), th)
                _tag(obj, space, KIND_AABB, ROLE_BOUNDARY, vi)
                made += 1
                core = _inset(aabb, depth) if depth > 0 else None
                if core is not None:
                    cobj = _box_obj(label + "_core", core, origin, axis, coll, KIND_AABB,
                                    ROLE_CORE, _material(KIND_AABB, ROLE_CORE), th)
                    _tag(cobj, space, KIND_AABB, ROLE_CORE, vi)
                    made += 1
            elif vol.kind == KIND_SPHERE:
                sph = vol.values
                r = float(sph[3])
                th = _tube(2.0 * r)
                obj = _sphere_obj(label, sph, origin, axis, coll, KIND_SPHERE, ROLE_BOUNDARY,
                                  _material(KIND_SPHERE, ROLE_BOUNDARY), th)
                _tag(obj, space, KIND_SPHERE, ROLE_BOUNDARY, vi)
                made += 1
                if depth > 0 and r > depth:
                    core = (sph[0], sph[1], sph[2], r - depth)
                    cobj = _sphere_obj(label + "_core", core, origin, axis, coll, KIND_SPHERE,
                                       ROLE_CORE, _material(KIND_SPHERE, ROLE_CORE), th)
                    _tag(cobj, space, KIND_SPHERE, ROLE_CORE, vi)
                    made += 1
    return coll, made


# ---------------------------------------------------------------- 写回
def _world_bounds(obj):
    """对象网格顶点的世界坐标轴对齐包围盒（含用户施加的移动/旋转/缩放）。"""
    mw = obj.matrix_world
    pts = [mw @ v.co for v in obj.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def _to_aircraft(co, origin, axis):
    x, y, z = acftool.from_blender(co, axis)
    return (x - origin[0], y - origin[1], z - origin[2])


def sync(doc, scene, origin, axis):
    """把 Blender 里对分区框的改动写回 Document 的行。返回 (改动体积数, 改动 blend 数, 警告)。

    设计取舍（这几条是刻意的，不是省事）：

      * **只认 boundary 对象**：core 框是 BLEND_DEPTH 的派生物，动它没有任何东西可写回。
      * **AABB 取"转完之后的世界包围盒"**：文件里只能存轴对齐盒，所以对象被旋转或非均匀
        缩放后，写回的是它的轴对齐外包盒 —— 这是语义正确的行为（X-Plane 也只认 AABB），
        不是"尽量贴近"。
      * **球取世界包围盒中心 + 最长边的一半**：这样即使施加了变换（apply rotation/scale）
        也算得对；非均匀缩放会警告，因为那已经不是一个球。
      * **同一个体积只认原对象**：`snd_owner_name` 与对象名不等 ⇒ Shift+D 出来的副本，
        跳过并警告。分区不支持新增体积，静默吞掉改动比拒绝更糟。
      * **BLEND_DEPTH 每个 space 只收一次**：多个体积的对象各带一份 `snd_blend_depth`，
        按体积顺序取第一个当权威值；数值不一致就警告（否则按对象逐个 patch 会互相改回去）。
      * 差值小于 TOL 当作没动 ⇒ 未编辑的文件导出仍逐字节相同。
    """
    geom = {}          # (space_index, volume_index) -> values
    blend_votes = {}   # space_index -> [(volume_index, value)]
    warns = []
    for obj in scene.objects:
        if "snd_space_index" not in obj or obj.get("snd_space_role") != ROLE_BOUNDARY:
            continue
        idx = int(obj["snd_space_index"])
        vi = int(obj.get("snd_volume_index", 0))
        if not (0 <= idx < len(doc.spaces)):
            warns.append("%s 指向不存在的 space %d，跳过" % (obj.name, idx))
            continue
        space = doc.spaces[idx]
        if not (0 <= vi < len(space.volumes)):
            warns.append("%s 指向不存在的体积（不支持新增体积），跳过" % obj.name)
            continue
        owner = obj.get("snd_owner_name")
        if owner and obj.name != owner:
            warns.append("%s 是复制出来的（原对象 %s），分区不支持新增体积，跳过"
                         % (obj.name, owner))
            continue
        if (idx, vi) in geom:
            warns.append("%s 与另一个对象指向同一个体积，跳过" % obj.name)
            continue

        vol = space.volumes[vi]
        lo, hi = _world_bounds(obj)
        if vol.kind == KIND_AABB:
            a = _to_aircraft(lo, origin, axis)
            b = _to_aircraft(hi, origin, axis)
            geom[(idx, vi)] = tuple(min(a[i], b[i]) for i in range(3)) + \
                              tuple(max(a[i], b[i]) for i in range(3))
        else:
            center = tuple((lo[i] + hi[i]) / 2.0 for i in range(3))
            sizes = [hi[i] - lo[i] for i in range(3)]
            if max(sizes) - min(sizes) > 0.01 * max(sizes):
                warns.append("%s 球体缩放不均匀（%.3f / %.3f / %.3f），半径取最长边的一半"
                             % ((obj.name,) + tuple(sizes)))
            geom[(idx, vi)] = _to_aircraft(center, origin, axis) + (max(sizes) / 2.0,)

        blend = obj.get("snd_blend_depth")
        if blend is not None:
            blend_votes.setdefault(idx, []).append((vi, float(blend)))

    changed_volumes = 0
    for (idx, vi), values in sorted(geom.items()):
        if doc.patch_space_volume(doc.spaces[idx], vi, values):
            changed_volumes += 1

    changed_blend = 0
    for idx, votes in sorted(blend_votes.items()):
        votes.sort()
        values = {round(v, 3) for _, v in votes}
        if len(values) > 1:
            warns.append("space %d 的多个体积带着不同的 snd_blend_depth %s，取体积 %d 的值"
                         % (idx, sorted(values), votes[0][0]))
        if doc.patch_space_blend(doc.spaces[idx], votes[0][1]):
            changed_blend += 1
    return changed_volumes, changed_blend, warns
