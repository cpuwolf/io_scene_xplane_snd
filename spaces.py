"""把 .snd 的 sound space（AABB / SPHERE）在 Blender 里画出来。

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
  * 不写 `snd_uid`：导出只认带 `snd_uid` 的对象，所以这些框永远不会被当成 attachment 写回。
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
    """统一后处理：材质 + Wireframe 管 + 透视可见 + 不被误选成 attachment。"""
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
    """AABB(minx,miny,minz,maxx,maxy,maxz) → 立方体网格；坐标 = 飞机坐标 + 原点，再按轴向模式转。"""
    mn, mx = aabb[:3], aabb[3:]
    xs = (mn[0], mx[0]); ys = (mn[1], mx[1]); zs = (mn[2], mx[2])
    corners = [(x, y, z) for x in xs for y in ys for z in zs]
    verts = [acftool.to_blender((c[0] + origin[0], c[1] + origin[1], c[2] + origin[2]), axis)
             for c in corners]
    # corners 顺序是 (x, y, z) 的二进制计数：0=(000) … 7=(111)
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
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


def _tag(obj, space, kind, role, volume_index):
    obj["snd_space_index"] = int(space.index)
    obj["snd_volume_index"] = int(volume_index)
    obj["snd_space_kind"] = kind
    obj["snd_space_role"] = role
    if space.sound_index is not None:
        obj["snd_sound_index"] = int(space.sound_index)
    if space.blend_depth is not None:
        obj["snd_blend_depth"] = float(space.blend_depth)
    # 这两个是给人看的：不在 snd_uid 里，所以导出时不会被当成 attachment
    obj["snd_space_line"] = int(space.begin_line) + 1
    if space.remark:
        obj["snd_space_area"] = space.remark
    obj["snd_readonly"] = True


def _tube(size):
    """线框管的粗细按体积尺寸的 0.5% 给：不管 3 m 的座舱还是 30 m 的客舱，屏幕上是同一个视觉重量。"""
    return max(0.008, min(0.2, size * 0.005))


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
        sound = "" if space.sound_index is None else "idx%d" % space.sound_index
        for vi, aabb in enumerate(space.aabbs):
            label = "SPACE_%02d_%s%s" % (space.index, area or "AABB", "_v%d" % vi if vi else "")
            size = max(max(aabb[i + 3] - aabb[i] for i in range(3)), 0.05)
            th = _tube(size)
            obj = _box_obj(label, aabb, origin, axis, coll, KIND_AABB, ROLE_BOUNDARY,
                           _material(KIND_AABB, ROLE_BOUNDARY), th)
            _tag(obj, space, KIND_AABB, ROLE_BOUNDARY, vi)
            made += 1
            core = _inset(aabb, depth) if depth > 0 else None
            if core is not None:
                cobj = _box_obj(label + "_core", core, origin, axis, coll, KIND_AABB, ROLE_CORE,
                                _material(KIND_AABB, ROLE_CORE), th)
                _tag(cobj, space, KIND_AABB, ROLE_CORE, vi)
                made += 1
        for vi, sph in enumerate(space.spheres):
            label = "SPACE_%02d_%s%s" % (space.index, area or "SPHERE", "_v%d" % vi if vi else "")
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
