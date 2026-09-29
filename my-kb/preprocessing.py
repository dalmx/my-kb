#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档预处理：frontmatter 解析 → MarkdownHeader 切分 → 长度二次切分 → 元数据合并

使用 python-frontmatter 替代手写 YAML 解析（修复多块误识别 bug）
使用 MarkdownHeaderTextSplitter 实现按标题语义切分（标题层级进入 metadata）
"""

import re
import datetime
import frontmatter  # python-frontmatter 库
from langchain_core.documents import Document

from config import (
    CHUNK_SIZE, CHUNK_OVERLAP, HEADERS_TO_SPLIT_ON,
    DEFAULT_CATEGORY, DEFAULT_MODULE, DEFAULT_FACTORY,
)


# ============ Frontmatter 解析（python-frontmatter 库） ============

def parse_frontmatter(content):
    """用 python-frontmatter 解析 YAML frontmatter，返回 (frontmatter_dict, body)。

    彻底替代手写解析，修复正文 --- 被误识别为 frontmatter 的 bug。
    无 frontmatter 的文件返回 ({}, content)。
    """
    try:
        post = frontmatter.loads(content)
        fm = dict(post.metadata)
        body = post.content
        # tags 统一为 list（frontmatter 库已自动解析 [a,b] 为 list）
        if "tags" in fm and isinstance(fm["tags"], str):
            fm["tags"] = [t.strip() for t in fm["tags"].split(",") if t.strip()]
        return fm, body
    except Exception:
        # frontmatter 解析失败时退化为原文（容错）
        return {}, content


# ============ 分块（MarkdownHeader 两阶段） ============

# 懒初始化：langchain_text_splitters 顶层会连带 import transformers+torch
# （单进程多占 ~400MB），仅在真正切分文档时才加载
_splitters = None


def _get_splitters():
    """返回 (header_splitter, size_splitter)，首次调用时构造并复用。"""
    global _splitters
    if _splitters is None:
        from langchain_text_splitters import (
            MarkdownHeaderTextSplitter,
            RecursiveCharacterTextSplitter,
        )
        # 阶段1：按标题语义切分（全局复用，避免重复构造）
        header = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADERS_TO_SPLIT_ON,
            strip_headers=False,   # 保留标题在正文中（阅读体验）
        )
        # 阶段2：超长 section 二次切分（全局复用）
        size = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
        )
        _splitters = (header, size)
    return _splitters


def _split_local(body):
    """本地两阶段切分（懒加载 splitter，冷机会话进程首次 ~分钟级 torch import）。

    仅供 split_document 兜底和 model_service 的 /split 端点调用——
    服务端必须走本函数而非 split_document，否则远程调用会回环打自己。
    """
    header_splitter, size_splitter = _get_splitters()
    # 阶段1：按标题切分（返回 Document 列表，metadata 含 h1/h2/h3）
    try:
        header_chunks = header_splitter.split_text(body)
    except Exception:
        # 极端情况（如空文档）：直接走长度切分
        header_chunks = [Document(page_content=body, metadata={})]

    if not header_chunks:
        return []

    # 阶段2：对每个 header chunk 做长度切分
    # split_documents 会保留原始 metadata 并分块
    return size_splitter.split_documents(header_chunks)


def split_document(body):
    """对正文做两阶段切分，返回 List[Document]。

    优先走共享模型服务的 /split 端点（服务进程 transformers 常驻热加载，
    会话进程零 torch——2026-08-23 实测冷机首次本地切分 torch import 达 122s
    触发写库超时，故切分上移）；服务不可用时回退本地懒加载路径。
    """
    try:
        from service_client import split_via_service
        chunks = split_via_service(body)
        if chunks is not None:
            return [Document(page_content=c['page_content'], metadata=c.get('metadata') or {})
                    for c in chunks]
    except Exception:
        pass  # 服务路径任何异常都静默回退本地
    return _split_local(body)


# ============ 元数据构建 ============

def build_chunk_metadata(filename, frontmatter_meta, header_meta=None, overrides=None):
    """构造写入向量库的 chunk metadata。

    参数：
        filename: 文件名（source）
        frontmatter_meta: frontmatter 字典（title/category/module/tags）
        header_meta: MarkdownHeaderTextSplitter 产生的标题层级 {h1,h2,h3}
        overrides: 显式覆盖值（优先级最高）

    返回 dict，包含：
        source/title/category/module/tags（文档级）
        h1/h2/h3（章节级，来自标题切分）
    """
    fm = frontmatter_meta or {}
    header = header_meta or {}
    ov = overrides or {}

    def _pick(name, default):
        # 优先级：显式覆盖 > frontmatter > 默认值
        if name in ov and ov[name] is not None:
            return ov[name]
        if name in fm and fm[name] is not None:
            return fm[name]
        return default

    meta = {
        "source": filename,
        "title": _pick("title", filename),
        "category": _pick("category", DEFAULT_CATEGORY),
        "module": _pick("module", DEFAULT_MODULE),
    }

    # tags 序列化为逗号串（Chroma metadata 不支持 list）
    tag_val = _pick("tags", [])
    if isinstance(tag_val, list):
        meta["tags"] = ",".join(str(t) for t in tag_val)
    else:
        meta["tags"] = str(tag_val)

    # 生命周期字段（可选，缺省 active / 空串，检索端按缺省处理）
    meta["status"] = str(_pick("status", "active")).strip().lower() or "active"
    meta["updated"] = str(_pick("updated", "")).strip()

    # 工厂/项目线字段（可选，缺省通用；业务文档应显式写明所属项目线）
    meta["factory"] = str(_pick("factory", DEFAULT_FACTORY)).strip() or DEFAULT_FACTORY

    # 章节级元数据（标题层级）
    meta["h1"] = str(header.get("h1", ""))
    meta["h2"] = str(header.get("h2", ""))
    meta["h3"] = str(header.get("h3", ""))

    return meta


def infer_title_from_h1(body, filename):
    """从正文的 H1 标题提取 title，提取不到则返回 filename。"""
    for line in body.split("\n"):
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return filename


def extract_summary(body, max_len=300):
    """提取 H1 后的引用摘要（连续 > 行），供 chunk 上下文前缀复用。

    与写入校验第 7 条同口径（H1 后两行内须有 > 摘要）；存量无摘要文档
    返回空串，前缀退化为仅 title。
    """
    lines = body.split("\n")
    h1_idx = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("# "):
            h1_idx = i
            break
    if h1_idx is None:
        return ""
    quote_parts = []
    for ln in lines[h1_idx + 1:]:
        s = ln.strip("\r").lstrip()
        if s.startswith(">"):
            quote_parts.append(s.lstrip("> ").strip())
        elif not s and not quote_parts:
            continue  # H1 与摘要之间的空行
        else:
            break  # 首个非引用实体行，摘要结束
    return " ".join(p for p in quote_parts if p)[:max_len]


# ============ 完整预处理入口 ============

def process_document(content, filename, overrides=None):
    """完整预处理：frontmatter 解析 → 分块 → 元数据合并。

    参数：
        content: 文件全文（含 frontmatter）
        filename: 文件名
        overrides: {category, module, tags} 显式覆盖 frontmatter

    返回 List[Document]，每个 Document 含完整 metadata（文档级 + 章节级）。
    """
    # 1. frontmatter 解析
    fm, body = parse_frontmatter(content)

    # title 兜底：frontmatter 无 title 时从 H1 提取
    if not fm.get("title"):
        fm["title"] = infer_title_from_h1(body, filename)

    # 2. 两阶段分块
    chunks = split_document(body)

    # 3. 合并元数据（frontmatter + 标题层级 + overrides）
    for chunk in chunks:
        chunk.metadata = build_chunk_metadata(
            filename=filename,
            frontmatter_meta=fm,
            header_meta=chunk.metadata,   # split_document 已注入 h1/h2/h3
            overrides=overrides,
        )

    # 4. 上下文前缀（Contextual Retrieval 弱化版）：title+摘要拼进每个 chunk 文本，
    #    前缀参与向量嵌入与 BM25，非首块章节获得文档级语义锚点（跨文档同章节名
    #    如各文档的"## 一、整体架构"互扰由此消解）。首块会与自带摘要冗余，可接受
    from config import CHUNK_CONTEXT_PREFIX
    if CHUNK_CONTEXT_PREFIX:
        summary = extract_summary(body)
        prefix = f"【{fm.get('title', filename)}】" + summary
        for chunk in chunks:
            chunk.page_content = f"{prefix}\n\n{chunk.page_content}"

    return chunks


# ============ 元数据过滤（检索时用） ============

def build_where_filter(category=None, module=None, tags=None, source=None, factory=None):
    """把可选的过滤条件组装成 Chroma 的 where 字典（AND 关系）。
    无任何条件时返回 None（不做过滤）。

    tags 为列表时按"命中任一即可"组装（$or + 每个标签一条 $contains），
    与工具描述契约一致；factory/category/module/source 等单值过滤行为不变。
    注意 Chroma 限制：$or/$and 键不能与其他字段键同层出现，
    故"多标签 + 其他条件"时整体包一层 $and。
    """
    conditions = {}
    if category:
        conditions["category"] = category
    if module:
        conditions["module"] = module
    if source:
        conditions["source"] = source
    if factory:
        conditions["factory"] = factory
    if tags:
        if isinstance(tags, str):
            tags = [tags]
        tag_list = list(dict.fromkeys(str(t).strip() for t in tags if str(t).strip()))
        if tag_list:
            # tags 在库里是逗号分隔串，用 $contains 做子串匹配
            # 否则精确匹配只有传整串 "A,B,C" 才命中
            tag_conds = [{"tags": {"$contains": t}} for t in tag_list]
            if len(tag_conds) == 1:
                # 单标签是普通字段条件，可与其他条件同层扁平；
                # Chroma 仅在 $or 与字段键同层时才要求 $and 包裹
                conditions["tags"] = {"$contains": tag_list[0]}
                return conditions
            tags_cond = {"$or": tag_conds}
            if conditions:
                return {"$and": [conditions, tags_cond]}
            return tags_cond
    return conditions or None


# ============ 内容工具（frontmatter 区段 / 合并拼接） ============

# 首个 --- 对（frontmatter 区段）：起始行 ---，到下一行首 --- 为止
_FM_SEGMENT_RE = re.compile(r'^---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|$)', re.S)


def frontmatter_segment(content):
    """返回首个 --- 对之间的 frontmatter 区段（含首尾 --- 行）；无 frontmatter 返回 ''。

    供"只在 frontmatter 内检测字段"的场景使用（如 save_markdown 判断
    updated/status 是否已填）——正文示例里出现的 `updated:` 不应被误判。
    """
    if not content.startswith("---"):
        return ""
    m = _FM_SEGMENT_RE.match(content)
    return m.group(0) if m else ""


def strip_leading_h1(body):
    """去掉正文开头（跳过头部空行后第一行）的 H1 标题行。

    合并拼接时各源剥掉自己的 H1，由合并文档统一出一个 H1（消除多 H1）。
    """
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith("# "):
            del lines[i]
        break
    return "\n".join(lines)


def build_merged_document(bodies, title, merged_from, base_fm=None, today=None):
    """把多个源正文拼接为规范合并文档（纯函数，不做 I/O）。返回完整文档字符串。

    - 单 H1：统一为 title（各源正文先经 strip_leading_h1 剥掉自己的 H1）
    - 文首摘要注明合并来源（纯文本文件名，不带反引号/链接语法——
      源文件随后会被删除，避免残留成断链或自引用）
    - frontmatter 以 base_fm 为基底（优先 target 既有 fm，缺省用第一个源的 fm），
      title 统一覆盖、updated 刷新为合并当日
    """
    today = today or datetime.date.today().isoformat()
    fm = dict(base_fm or {})
    fm["title"] = title
    fm["updated"] = today

    note = ("> 合并说明: 本文由 "
            + "、".join(str(s) for s in merged_from)
            + f" 合并而成（合并日期 {today}），原各文档章节以 --- 分隔。")

    # H1 后单个空行接摘要行（格式校验要求 H1 后两行内出现 `>`）
    head = f"# {title}\n\n{note}"
    parts = [strip_leading_h1(b).strip("\n") for b in bodies]
    body = head + "\n\n---\n\n" + "\n\n---\n\n".join(parts)

    post = frontmatter.Post(body, **fm)
    return frontmatter.dumps(post)


# ============ 文档格式校验（写入时强制约束） ============

# 章节中文序号合法首字符（中文数字）
_CN_NUMERAL_HEADS = "一二三四五六七八九十百"

# 围栏行：>=3 个反引号开头（CommonMark：闭合行须 >= 开栏长度且后随空白）
_FENCE_LINE_RE = re.compile(r"^(`{3,})(.*)$")


def _scan_body_structure(body):
    """单趟扫描正文结构（围栏状态机），供格式校验复用。返回 dict：

    - first_h1_lineno / first_h1_text: 围栏外第一个 H1 的行号（1 计）与标题文本
    - h2_sections: [(行号, 标题文本)] 围栏外全部 `## ` 章节
    - bare_fences: [行号] 开栏未标语言的裸围栏

    围栏判定按 CommonMark：开栏行后可跟语言/info 串，闭合行反引号数须
    >= 开栏长度且后随空白；围栏内的 `#` / `##` 行是代码内容，不计入标题。
    """
    first_h1_lineno = None
    first_h1_text = None
    h2_sections = []
    bare_fences = []
    fence_len = 0  # 0=不在围栏内，否则为开栏反引号数
    for lineno, raw in enumerate(body.split("\n"), start=1):
        stripped = raw.strip("\r").lstrip()
        m = _FENCE_LINE_RE.match(stripped)
        if m:
            ticks, info = m.group(1), m.group(2).strip()
            if fence_len:
                if len(ticks) >= fence_len and not info:
                    fence_len = 0  # 合法闭合行（不查语言）
            else:
                if not info:
                    bare_fences.append(lineno)
                fence_len = len(ticks)
            continue
        if fence_len:
            continue
        if first_h1_lineno is None and stripped.startswith("# "):
            first_h1_lineno = lineno
            first_h1_text = stripped[2:].strip()
        elif stripped.startswith("## "):
            h2_sections.append((lineno, stripped[3:].strip()))
    return {
        "first_h1_lineno": first_h1_lineno,
        "first_h1_text": first_h1_text,
        "h2_sections": h2_sections,
        "bare_fences": bare_fences,
    }


def validate_doc_format(content, for_append=False):
    """校验 Markdown 文档是否符合知识库格式规范（9 条硬校验）。

    校验规则：
    1. 必须有 frontmatter（--- 开头 + --- 闭合）
    2. 必须有 title / category / module / tags 四个字段
    3. category 必须是合法枚举值
    4. tags 至少 3 个
    5. 必须有 H1 标题（# 开头）
    6. H1 与 title 一致（strip 后比较）
    7. H1 后两行内有 `>` 引用摘要
    8. `## ` 章节标题用中文序号（首字符为中文数字；全文无 `## ` 章节的短文不强制）
    9. 代码开栏围栏标注语言（状态机区分开栏/闭合行，只查开栏）

    for_append=True（append_section 场景）：豁免第 6/7 条对存量文档的拦截——
    往旧文档追加内容不应被其历史结构债卡死；第 8/9 条照常校验
    （追加内容自身的章节序号与围栏语言必须合规）。

    返回 (ok: bool, errors: list[str])
    ok=True 表示通过，errors 为空列表
    ok=False 表示不通过，errors 为错误描述列表
    """
    from config import (
        CATEGORY_PATTERN, KNOWN_CATEGORIES, REQUIRED_FM_FIELDS, MIN_TAGS_COUNT,
        VALID_STATUS,
    )

    errors = []

    # 1. frontmatter 解析
    try:
        fm, body = parse_frontmatter(content)
    except Exception as e:
        return False, [f"frontmatter 解析失败: {e}"]

    # 检查是否真的解析出了 frontmatter（空 dict 说明没有 frontmatter）
    if not fm:
        errors.append(
            "缺少 frontmatter。文档必须以 YAML frontmatter 开头，格式：\n"
            "---\n"
            'title: 文档标题\n'
            "category: 技术-.NET\n"
            "module: Ext.NET\n"
            "tags: [关键词1, 关键词2, 关键词3]\n"
            "---"
        )
        return False, errors

    # 2. 必填字段检查
    for field in REQUIRED_FM_FIELDS:
        val = fm.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"frontmatter 缺少必填字段: {field}")

    # 3. category 格式校验（二段式命名，不限制具体值）
    cat = fm.get("category")
    if cat and not CATEGORY_PATTERN.match(str(cat)):
        errors.append(
            f"category '{cat}' 格式不合法。必须是以下之一：\n"
            f"  - 技术-XXX（如 技术-.NET / 技术-数据库）\n"
            f"  - 业务-XXX（如 业务-通用 / 业务-模具）\n"
            f"  - 部署运维 / 未分类\n"
            f"现有分类参考: {', '.join(sorted(KNOWN_CATEGORIES))}"
        )

    # 4. tags 数量校验
    tags_val = fm.get("tags")
    if tags_val is not None:
        if isinstance(tags_val, str):
            tag_list = [t.strip() for t in tags_val.split(",") if t.strip()]
        elif isinstance(tags_val, list):
            tag_list = tags_val
        else:
            tag_list = []
        if len(tag_list) < MIN_TAGS_COUNT:
            errors.append(
                f"tags 至少需要 {MIN_TAGS_COUNT} 个，当前只有 {len(tag_list)} 个"
            )

    # 5. H1 标题检查
    has_h1 = any(line.lstrip().startswith("# ") for line in body.split("\n"))
    if not has_h1:
        errors.append("正文缺少 H1 标题（# 开头），H1 应与 title 一致或同义")

    # 单趟扫描正文结构（围栏状态机），6-9 条共用
    struct = _scan_body_structure(body)

    # 6. H1 与 title 一致（strip 后比较）；append 场景豁免（存量债不拦追加）
    title_val = fm.get("title")
    if (not for_append and isinstance(title_val, str) and title_val.strip()
            and struct["first_h1_text"] is not None):
        if struct["first_h1_text"] != title_val.strip():
            errors.append(
                f"H1 标题与 title 不一致: H1 为 '{struct['first_h1_text']}'，"
                f"title 为 '{title_val.strip()}'。H1 应与 frontmatter title 完全一致"
                "（检索元数据以 title 为锚点）"
            )

    # 7. H1 后两行内有 `>` 引用摘要；append 场景豁免（存量债不拦追加）
    if not for_append and struct["first_h1_lineno"] is not None:
        lines = body.split("\n")
        h1_idx = struct["first_h1_lineno"] - 1
        window = lines[h1_idx + 1: h1_idx + 3]
        if not any(ln.strip("\r").lstrip().startswith(">") for ln in window):
            errors.append(
                f"H1（:{struct['first_h1_lineno']}）后两行内缺少 '> ' 引用摘要，"
                "应在 H1 后紧跟一两句概括（向量分块首块的语义锚点）"
            )

    # 8. `## ` 章节标题中文序号（首字符须为中文数字）；全文无 ## 章节的短文不强制
    if struct["h2_sections"]:
        bad_sections = [(ln, t) for ln, t in struct["h2_sections"]
                        if not t or t[0] not in _CN_NUMERAL_HEADS]
        if bad_sections:
            shown = "; ".join(f":{ln} '## {t}'" for ln, t in bad_sections[:5])
            more = f" 等 {len(bad_sections)} 处" if len(bad_sections) > 5 else ""
            errors.append(
                f"`## ` 章节标题须用中文序号（## 一、## 二、…，首字符为中文数字）。"
                f"违规: {shown}{more}"
            )

    # 9. 代码开栏围栏标注语言（状态机只查开栏，闭合行裸 ``` 属正常）
    if struct["bare_fences"]:
        shown = ", ".join(f":{ln}" for ln in struct["bare_fences"][:8])
        more = f" 等 {len(struct['bare_fences'])} 处" if len(struct["bare_fences"]) > 8 else ""
        errors.append(
            "代码开栏围栏必须标注语言（```python / ```sql / ```aspx）。"
            f"裸开栏: {shown}{more}"
        )

    # 10. 生命周期字段（可选：updated 最后确认有效日期 / status 状态位）
    status_val = fm.get("status")
    if status_val is not None and str(status_val).strip().lower() not in VALID_STATUS:
        errors.append(
            f"status '{status_val}' 不合法，必须是 active/deprecated/archived 之一"
            "（缺省视为 active；deprecated 仍可被检索但结果会标注已废弃）"
        )
    updated_val = fm.get("updated")
    if updated_val is not None:
        try:
            datetime.date.fromisoformat(str(updated_val).strip())
        except ValueError:
            errors.append(
                f"updated '{updated_val}' 格式不合法，必须是 YYYY-MM-DD（如 2026-08-14，最后确认有效日期）"
            )

    return len(errors) == 0, errors
