"""CI 静态检查（不需要 Blender）：语法 + 扩展元数据 + 不该提交的文件。

  python3 tests/ci_lint.py
"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "dist", "__pycache__", ".idea", ".vscode"}
errors = []

# 1) 所有 .py 能 parse
for f in sorted(ROOT.rglob("*.py")):
    if any(part in SKIP_DIRS for part in f.parts):
        continue
    try:
        ast.parse(f.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append("%s: %s" % (f.relative_to(ROOT), exc))

# 2) manifest 必填字段
manifest_path = ROOT / "blender_manifest.toml"
if not manifest_path.is_file():
    errors.append("缺 blender_manifest.toml")
else:
    manifest = manifest_path.read_text(encoding="utf-8")
    for key in ("schema_version", "id", "version", "name", "tagline", "maintainer",
                "type", "tags", "license", "blender_version_min"):
        if not re.search(r"^%s\s*=" % key, manifest, re.M):
            errors.append("manifest 缺字段: %s" % key)

    # id 必须和目录名一致（扩展审核会查）
    m = re.search(r'^id\s*=\s*"([^"]+)"', manifest, re.M)
    if m and m.group(1) != ROOT.name:
        errors.append("manifest id (%s) 与目录名 (%s) 不一致" % (m.group(1), ROOT.name))

    # 4.2+ 不再接受的标签
    if '"Game Engine"' in manifest:
        errors.append('tags 里含 "Game Engine"（4.2+ 已不接受）')

    # 版本号必须是点分数字
    m = re.search(r'^version\s*=\s*"([^"]+)"', manifest, re.M)
    if m and not re.fullmatch(r"\d+(\.\d+){1,2}", m.group(1)):
        errors.append("manifest version 不是 x.y(.z): %r" % m.group(1))

    # 许可证必须是 SPDX 形式
    if 'license = ["SPDX:' not in manifest:
        errors.append("license 必须写成 SPDX:<id> 列表")

# 3) 扩展包不应该带 bl_info（元数据在 manifest 里）
init = ROOT / "__init__.py"
if init.is_file() and re.search(r"^bl_info\s*=", init.read_text(encoding="utf-8"), re.M):
    errors.append("__init__.py 仍有 bl_info —— 扩展应由 manifest 提供元数据")

# 4) 不该提交的文件
banned_ext = {".zip", ".blend", ".blend1", ".pyc", ".bank"}
for f in sorted(ROOT.rglob("*")):
    if any(part in SKIP_DIRS for part in f.parts):
        continue
    if f.is_file() and f.suffix in banned_ext:
        errors.append("仓库里不该有: %s" % f.relative_to(ROOT))

# 5) 每个提交的文件都能 UTF-8 解码
for f in sorted(ROOT.rglob("*")):
    if not f.is_file() or any(part in SKIP_DIRS for part in f.parts):
        continue
    try:
        f.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append("非 UTF-8 文件: %s" % f.relative_to(ROOT))

if errors:
    print("LINT FAIL")
    for e in errors:
        print("  - " + e)
    sys.exit(1)
print("LINT OK  (%d python files, manifest/package checks passed)" % len(list(ROOT.rglob("*.py"))))
