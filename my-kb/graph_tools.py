#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档图分析：断链检查 / 孤岛分析 / 引用更新 / 文件移动合并

这些是 LangChain 无对应组件的定制业务逻辑，原样从 server.py 迁移。
"""

import datetime
import re
from pathlib import Path

from config import KB_ROOT, ALLOWED_KB_IDS, STALE_DAYS
from utils import log

# 匹配反引号包裹的 .md 文件名引用
_MD_REF_PATTERN = re.compile(r'`([a-zA-Z0-9_.\-\u4e00-\u9fff]+\.md)`')
# 匹配 [[wikilink]] 引用（可带可不带 .md 后缀；别名 [[a|b]] 与锚点 [[a#b]] 不识别，维持原状）
_WIKILINK_PATTERN = re.compile(r'\[\[([^\]|#]+?)\]\]')
# 匹配 Markdown 链接 ](x.md)（可带 #锚点；排除 / : \ 避免 URL/子路径误报）
_MD_LINK_PATTERN = re.compile(r'\]\(([^)\s/:\\]+?\.md)(#[^)\s]*)?\)')
# 2026-08-28 C1/C2/C3 修复：此前 update_references/check_broken_links/compute_reference_graph
# 只认反引号形态，wikilink 与 md 链接引用在改名/合并后悬空成断链、又不在断链巡检覆盖内。
# 三处统一改用 extract_all_references / replace_references（三形态公共提取/替换）。


def _normalize_ref_name(name):
    """引用名规范化：去首尾空白并统一补 .md 后缀。"""
    name = str(name or "").strip()
    if name and not name.endswith(".md"):
        name += ".md"
    return name


def extract_md_references(content):
    """从 markdown 内容中提取所有反引号包裹的 .md 文件名引用。返回 set。

    仅反引号形态（历史接口，保留兼容）；三形态统一提取用 extract_all_references。
    """
    return set(m.group(1) for m in _MD_REF_PATTERN.finditer(content))


def extract_all_references(content):
    """提取全部引用（三形态：反引号 .md / [[wikilink]] / ](x.md) 链接），统一补 .md 后缀。返回 set。"""
    refs = set(extract_md_references(content))
    for m in _WIKILINK_PATTERN.finditer(content):
        name = m.group(1).strip()
        if name:
            refs.add(name if name.endswith(".md") else name + ".md")
    for m in _MD_LINK_PATTERN.finditer(content):
        refs.add(m.group(1))
    return refs


def replace_references(content, old_name, new_name):
    """把 content 中三形态的 old_name 引用全部改写为 new_name。返回 (新content, 替换次数)。

    三形态：反引号 `old.md`、[[wikilink]]（带/不带 .md，保持原后缀风格）、
    Markdown 链接 ](old.md)（保留 #锚点）。old/new 可不带 .md 后缀（内部统一规范化）。
    """
    old_ref = _normalize_ref_name(old_name)
    new_ref = _normalize_ref_name(new_name)
    if not old_ref or not new_ref or old_ref == new_ref:
        return content, 0
    old_stem, new_stem = old_ref[:-3], new_ref[:-3]
    count = 0

    # 1) 反引号 `old.md` → `new.md`
    content, n = re.subn(rf'`{re.escape(old_ref)}`', f'`{new_ref}`', content)
    count += n

    # 2) wikilink [[old]] / [[old.md]] → [[new]] / [[new.md]]（保持原后缀风格）
    def _wikilink_repl(m):
        return f"[[{new_ref}]]" if m.group(1).strip().endswith(".md") else f"[[{new_stem}]]"
    content, n = re.subn(
        rf'\[\[\s*({re.escape(old_stem)}(?:\.md)?)\s*\]\]',
        _wikilink_repl, content)
    count += n

    # 3) Markdown 链接 ](old.md) / ](old.md#锚点) → ](new.md)，锚点原样保留
    content, n = re.subn(
        rf'\]\({re.escape(old_ref)}(#[^)\s]*)?\)',
        lambda m: f"]({new_ref}{m.group(1) or ''})", content)
    count += n

    return content, count


def scan_md_files(kb_id):
    """扫描指定知识库 raw/markdown 目录下的所有 .md 文件，返回 list[Path]。"""
    md_dir = KB_ROOT / kb_id / "raw" / "markdown"
    if not md_dir.exists():
        return []
    return sorted(md_dir.glob("*.md"))


def update_references(kb_id, old_name, new_name):
    """扫描指定库所有 .md，把三形态引用（反引号 / [[wikilink]] / ](x.md) 链接）old_name
    替换为 new_name。返回修改文件数。"""
    changed = 0
    for md_file in scan_md_files(kb_id):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
            new_content, n = replace_references(content, old_name, new_name)
            if n > 0:
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                changed += 1
                log(f"更新引用: {md_file.name} ({old_name} → {new_name}, {n} 处)")
        except Exception as e:
            log(f"更新引用时出错 {md_file.name}: {e}")
    return changed


def all_kb_md_filenames():
    """返回所有知识库下的 .md 文件名 {filename: kb_id} 映射（用于跨库断链判断）。"""
    result = {}
    for kb_id in ALLOWED_KB_IDS:
        for md_file in scan_md_files(kb_id):
            result[md_file.name] = kb_id
    return result


def compute_reference_graph(kb_id):
    """计算引用图。返回 (in_degree, out_degree, all_files)。"""
    md_files = scan_md_files(kb_id)
    all_filenames = {f.name for f in md_files}
    in_degree = {fn: 0 for fn in all_filenames}
    out_degree = {fn: 0 for fn in all_filenames}

    for md_file in md_files:
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        refs = extract_all_references(content)
        local_refs = refs & all_filenames
        out_degree[md_file.name] = len(local_refs)
        for ref in local_refs:
            if ref != md_file.name:
                in_degree[ref] = in_degree.get(ref, 0) + 1

    return in_degree, out_degree, [f.name for f in md_files]


def check_broken_links(kb_ids):
    """断链检查。kb_ids: 要检查的库列表。
    返回格式化的断链报告文本。
    """
    all_files_map = all_kb_md_filenames()

    cross_ref = []      # 跨库引用（目标在其它知识库，正常）
    truly_missing = []  # 真缺失（所有库都找不到）

    for cur_kb in kb_ids:
        for md_file in scan_md_files(cur_kb):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            refs = extract_all_references(content)
            for ref in refs:
                if ref in all_files_map:
                    target_kb = all_files_map[ref]
                    if target_kb != cur_kb:
                        cross_ref.append((md_file.name, ref, target_kb))
                else:
                    truly_missing.append((md_file.name, ref))

    lines = ["断链检查报告:"]
    if cross_ref:
        lines.append(f"\n✅ 跨库引用 ({len(cross_ref)} 条，正常 — 目标在其它知识库真实存在):")
        for src, ref, target_kb in sorted(cross_ref):
            lines.append(f"  {src} → {ref} (在 {target_kb})")
    if truly_missing:
        lines.append(f"\n❌ 真缺失 ({len(truly_missing)} 条，需修复 — 所有库都找不到):")
        for src, ref in sorted(truly_missing):
            lines.append(f"  {src} → {ref}")

    if not cross_ref and not truly_missing:
        lines.append("\n✅ 全部引用均有效，无断链。")
        return "\n".join(lines)

    if truly_missing:
        lines.append(f"\n⚠️ 结论: 有 {len(truly_missing)} 条真缺失需修复，跨库引用 {len(cross_ref)} 条为正常。")
    else:
        lines.append(f"\n✅ 结论: 无需修复（真缺失 0 条）。跨库引用 {len(cross_ref)} 条均正常。")
    return "\n".join(lines)


def get_orphans(kb_id):
    """孤岛/枢纽分析 + 淘汰候选（零命中+孤岛，信息较旧者优先）。返回格式化报告。"""
    in_degree, out_degree, all_files = compute_reference_graph(kb_id)

    orphans = [f for f in all_files if in_degree.get(f, 0) == 0]
    hubs = [(f, in_degree[f]) for f in all_files if in_degree.get(f, 0) >= 3]
    hubs.sort(key=lambda x: -x[1])

    lines = [f"引用分析（库 {kb_id}，共 {len(all_files)} 个文件）:"]
    lines.append(f"\n孤岛文档 (入度=0，未被引用，{len(orphans)} 个):")
    for f in sorted(orphans):
        lines.append(f"  {f} (引用他人 {out_degree.get(f, 0)})")
    lines.append(f"\n枢纽文档 (入度≥3，被高频引用，{len(hubs)} 个):")
    for f, cnt in hubs:
        lines.append(f"  {f} (被引用 {cnt} 次)")

    # 淘汰候选：孤岛 且 检索零命中（自命中计数起点），按时效排序供人工复核
    from preprocessing import parse_frontmatter
    try:
        from hit_stats import load_hit_stats
        hs = load_hit_stats()
        hits_map = {s: int(e.get("hits", 0)) for s, e in hs.get("sources", {}).items()}
        since = str(hs.get("counting_since", "?"))
    except Exception:
        hits_map, since = {}, "?"

    candidates = []  # (排序组: 0=较旧 1=未标updated 2=近期更新, 文件名, 标注)
    today = datetime.date.today()
    for f in orphans:
        if hits_map.get(f, 0) != 0:
            continue
        updated, status = "", "active"
        try:
            with open(KB_ROOT / kb_id / "raw" / "markdown" / f, "r", encoding="utf-8") as fh:
                fm, _ = parse_frontmatter(fh.read())
            updated = str(fm.get("updated") or "")
            status = str(fm.get("status") or "active").lower()
        except Exception:
            pass
        age = None
        if updated:
            try:
                age = (today - datetime.date.fromisoformat(updated)).days
            except ValueError:
                pass
        if age is not None and age > STALE_DAYS:
            group, mark = 0, f"⏳较旧（更新于{updated}，已{age}天）"
        elif updated:
            group, mark = 2, f"更新于{updated}"
        else:
            group, mark = 1, "无 updated 字段（时效未确认）"
        if status != "active":
            mark += f" ⚠️{status}"
        candidates.append((group, f, mark))

    lines.append(f"\n淘汰候选（孤岛 + 零命中，较旧优先，共 {len(candidates)} 个，供人工复核）:")
    if candidates:
        for group, f, mark in sorted(candidates):
            lines.append(f"  {f} — {mark} (引用他人 {out_degree.get(f, 0)})")
    else:
        lines.append("  （无 — 孤岛文档近期均有检索命中）")
    lines.append(f"\n注: 命中计数自 {since} 起，需积累一段时间后零命中结论才可靠；淘汰决策始终留人工。")
    return "\n".join(lines)


# ============ 文档目录展开（结构寻址兜底层） ============

def build_outline(source):
    """展开指定文档的章节目录（h1/h2/h3 标题树 + 摘要）。返回格式化文本。

    低置信兜底的 coarse-to-fine 寻址：list_sources 找到对题文件名后，
    用本函数展开目录定位具体章节，再按章节标题反写查询或 get_source 直取该节。
    直接读 raw markdown 原文（不查向量库），标题顺序天然正确；跨库定位与 get_related 一致。
    """
    if not source:
        return "错误: 文件名不能为空"
    source = source if source.endswith(".md") else source + ".md"

    target_path, target_kb = None, None
    for kid in sorted(ALLOWED_KB_IDS):
        p = KB_ROOT / kid / "raw" / "markdown" / source
        if p.exists():
            target_path, target_kb = p, kid
            break
    if target_path is None:
        return f"错误: 所有库中均未找到 {source}"

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"错误: 读取文件失败 - {e}"

    from preprocessing import parse_frontmatter
    fm, body = parse_frontmatter(content)

    # 摘要 = H1 后首个引用块（格式规范第 5 条，语义锚点；H1 与摘要间常隔空行）
    summary = ""
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith(">"):
            summary = s.lstrip("> ").strip()
        break  # 只看 H1 后第一处非空行（引用摘要或首段）

    # 标题树：逐行扫，跳过代码围栏内的伪标题（示例 markdown 常见）；
    # 匹配原始行且仅允许 ≤3 空格缩进（ATX 规范），4+ 空格=缩进代码块不算标题
    # （P4，CC 审查 20260908）
    headings = []  # (level, text)
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^ {0,3}(#{1,3})\s+(.+?)\s*$", line)
        if m:
            headings.append((len(m.group(1)), m.group(2)))

    lines = [f"文档目录: {source} (库 {target_kb})"]
    meta_parts = [f"标题: {fm.get('title') or source}"]
    for k in ("category", "module"):
        if fm.get(k):
            meta_parts.append(f"{ {'category': '分类', 'module': '模块'}[k] }: {fm[k]}")
    if fm.get("tags"):
        tags = fm["tags"]
        tag_s = ", ".join(tags) if isinstance(tags, list) else str(tags)
        meta_parts.append(f"标签: {tag_s}")
    lines.append(" | ".join(meta_parts))
    if summary:
        lines.append(f"摘要: {summary}")

    lines.append(f"\n章节树 ({len(headings)} 个标题):")
    if headings:
        for level, text in headings:
            lines.append(f"{'  ' * (level - 1)}- {'#' * level} {text}")
    else:
        lines.append("  （无标题层级——短文或非结构化文档，请用 get_source 读全文）")

    lines.append(
        "\n使用建议: 对题章节 → 按该章节标题（含专有名词）反写查询再 search 一次，"
        "或 get_source 读全文定位该节。")
    return "\n".join(lines)


# ============ 引用图导航（Agentic RAG 多跳检索入口） ============

def _read_doc_info(path):
    """读取单个文档的 frontmatter 概要。返回 dict（失败返回空 dict）。"""
    try:
        from preprocessing import parse_frontmatter
        with open(path, "r", encoding="utf-8") as f:
            fm, _ = parse_frontmatter(f.read())
        return fm
    except Exception:
        return {}


def _fmt_doc_line(name, kb, fm, all_files_map):
    """格式化一条关联文档行：`文件名` (库) 标题 + 状态/断链标记。"""
    title = fm.get("title") or ""
    status = str(fm.get("status") or "active").lower()
    parts = [f"- `{name}` (库 {kb})"]
    if title and title != name:
        parts.append(f"标题: {title}")
    if name not in all_files_map:
        parts.append("⚠️未找到（断链）")
    elif status == "deprecated":
        parts.append("⚠️已废弃")
    elif status == "archived":
        parts.append("⚠️已归档")
    updated = str(fm.get("updated") or "")
    if updated:
        parts.append(f"更新: {updated}")
    return " | ".join(parts)


def get_related_docs(source):
    """引用图导航：返回指定文档的出链/入链/同模块近邻（跨所有库）。

    多跳检索入口：search 命中文档后，用本工具发现上下游关联文档，
    再用 get_source 取全文。引用识别包含反引号 .md、[[wikilink]] 和 ](x.md) 链接三种。
    """
    if not source:
        return "错误: 文件名不能为空"
    source = source if source.endswith(".md") else source + ".md"

    # 定位目标文档（跨库）
    target_path, target_kb = None, None
    for kid in sorted(ALLOWED_KB_IDS):
        p = KB_ROOT / kid / "raw" / "markdown" / source
        if p.exists():
            target_path, target_kb = p, kid
            break
    if target_path is None:
        return f"错误: 所有库中均未找到 {source}"

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            target_content = f.read()
    except Exception as e:
        return f"错误: 读取文件失败 - {e}"

    target_fm = _read_doc_info(target_path)
    out_refs = extract_all_references(target_content) - {source}
    all_files_map = all_kb_md_filenames()

    # 单次全库扫描：入链 + 同模块近邻（一并收集 frontmatter 概要）
    module = str(target_fm.get("module") or "").strip()
    in_links = []   # (name, kb, fm)
    same_module = []  # (name, kb, fm)
    for kid in sorted(ALLOWED_KB_IDS):
        for md_file in scan_md_files(kid):
            if md_file.name == source and kid == target_kb:
                continue
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    c = f.read()
            except Exception:
                continue
            fm = _read_doc_info(md_file)
            if source in extract_all_references(c):
                in_links.append((md_file.name, kid, fm))
            if module and str(fm.get("module") or "").strip() == module:
                same_module.append((md_file.name, kid, fm))

    # 出链目标解析（跨库查文件名→库与 frontmatter）
    out_links = []
    for ref in sorted(out_refs):
        ref_kb = all_files_map.get(ref)
        if ref_kb:
            ref_fm = _read_doc_info(KB_ROOT / ref_kb / "raw" / "markdown" / ref)
        else:
            ref_kb, ref_fm = "?", {}
        out_links.append((ref, ref_kb, ref_fm))

    # 同模块近邻排除已列出的出/入链文档，最多 10 条
    listed = {n for n, _, _ in out_links} | {n for n, _, _ in in_links}
    neighbors = [(n, k, f) for n, k, f in same_module if n not in listed][:10]

    lines = [f"文档关联分析: {source} (库 {target_kb})"]
    base = f"标题: {target_fm.get('title', source)}"
    if module:
        base += f" | 模块: {module}"
    base += f" | 状态: {str(target_fm.get('status') or 'active').lower()}"
    if target_fm.get("updated"):
        base += f" | 更新: {target_fm.get('updated')}"
    lines.append(base)

    lines.append(f"\n出链文档（本文引用的，{len(out_links)} 个）:")
    if out_links:
        lines.extend(_fmt_doc_line(n, k, f, all_files_map) for n, k, f in out_links)
    else:
        lines.append("  （无）")

    lines.append(f"\n入链文档（引用本文的，{len(in_links)} 个）:")
    if in_links:
        lines.extend(_fmt_doc_line(n, k, f, all_files_map) for n, k, f in sorted(in_links))
    else:
        lines.append("  （无）")

    label = f"（module={module}，" if module else "（"
    lines.append(f"\n同模块近邻{label}最多 10 个）:")
    if neighbors:
        lines.extend(_fmt_doc_line(n, k, f, all_files_map) for n, k, f in neighbors)
    else:
        lines.append("  （无）")

    lines.append("\n多跳检索建议: 对以上文档用 get_source 取全文，或用其标题关键词 search_knowledge。")
    return "\n".join(lines)
