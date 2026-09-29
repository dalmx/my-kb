#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检索引擎：混合召回（向量+BM25 RRF融合）→ 规则重排（标题/标签/h1/h2加权）→ cross-encoder 精排"""

from config import (
    DEFAULT_SEARCH_KB_IDS, ALLOWED_KB_IDS, DEFAULT_CATEGORY, DEFAULT_MODULE,
    ENABLE_HYBRID_SEARCH, RRF_K, MMR_MAX_PER_SOURCE, RERANK_POOL_K,
    CONFIDENCE_HIGH, CONFIDENCE_LOW, STALE_DAYS,
    GAP_LOG_ENABLED, GAP_LOG_PATH, GAP_LOG_DEDUPE_HOURS,
    RULE_H3_ENABLED, RULE_H3_WEIGHT,
    SECTION_INDEX_ENABLED, SECTION_TOP_K, SECTION_BOOST,
)
from models import get_vectorstore, get_reranker, get_embeddings, vector_mode, warmup_busy, WarmupBusyError
from service_client import bm25_query
from preprocessing import build_where_filter
from hit_stats import record_hits
from utils import log, validate_kb_id
import datetime
import json
import time

# 缺口日志进程内去重表：{查询文本key: 上次记录时间戳}
_gap_logged = {}


class KnowledgeRetriever:
    """三层检索 pipeline，可降级。"""

    def __init__(self):
        # sections 粗索引寻址信号：本轮检索命中的 (source, h2) 章节键集合，
        # 由 _hybrid_recall 填充（SECTION_INDEX_ENABLED 时），规则重排层消费
        self._section_keys = set()

    def _reset_section_keys(self):
        """每次检索入口清空章节信号（multi 检索内多次召回取并集）。"""
        self._section_keys = set()

    def search(self, query, n_results=5, kb_id=None, category=None, module=None, tags=None, factory=None):
        """执行三层检索，返回 (results_text, top_hits)。

        top_hits = [(score, doc, kb_id)]
          - 用 reranker 时 score = 相关性概率（越高越相关）
          - 降级时 score = 规则调整后距离（越小越相似）
        """
        if warmup_busy():
            raise WarmupBusyError(
                "知识库预热中（本地降级路径冷启动约 1~3 分钟），请稍后重试；"
                "共享服务正常时不走此路径")
        self._reset_section_keys()
        where = build_where_filter(category=category, module=module, tags=tags, factory=factory)

        # 1. 决定检索库
        if kb_id:
            validate_kb_id(kb_id)
            target_kbs = [kb_id]
        else:
            target_kbs = [k for k in DEFAULT_SEARCH_KB_IDS if k in ALLOWED_KB_IDS]

        # 2. 混合召回：向量 + BM25（RRF 融合）
        if ENABLE_HYBRID_SEARCH:
            all_hits = self._hybrid_recall(query, target_kbs, n_results, where)
        else:
            all_hits = self._vector_recall(query, target_kbs, n_results, where)

        if not all_hits:
            return self._empty_recall_message()

        # 3. 第一层：规则重排（标题/标签/h1/h2 加权）
        rule_ranked = self._rule_rerank(query, all_hits)

        # 4. 第二层：cross-encoder 精排
        # rerank_pool 元素统一为 (display_score, doc, kb_id)
        #   - 用 reranker 时 display_score = 相关性概率（越高越相关）
        #   - 降级时 display_score = 规则调整后距离（越小越相似）
        rerank_pool = rule_ranked[:RERANK_POOL_K]
        reranker = get_reranker()
        if reranker is not None and len(rerank_pool) > 1:
            try:
                pairs = [(query, doc.page_content[:1000]) for _, doc, _ in rerank_pool]
                scores = reranker.predict(pairs)
                scored = list(zip(scores, rerank_pool))
                scored.sort(key=lambda x: -x[0])
                # 把 reranker 分数带进排序后的候选（替代规则距离）
                ranked = [(float(rscore), doc, cur_kb) for rscore, (_, doc, cur_kb) in scored]
                used_reranker = True
            except Exception as e:
                log(f"reranker 推理失败，降级到规则重排: {e}")
                ranked = rerank_pool
                used_reranker = False
        else:
            ranked = rerank_pool
            used_reranker = False

        # 5. MMR 去冗余：从排好序的候选里挑 n_results 条，同 source 不超过阈值
        top = self._mmr_select(ranked, n_results)

        # 命中统计（Agentic RAG 方向六：淘汰决策数据源，失败不影响检索）
        if top:
            record_hits({item[1].metadata.get("source", "") for item in top})

        # 低置信检索记入缺口日志（Agentic 反思信号，供回顾补文档）
        if used_reranker and top and top[0][0] < CONFIDENCE_LOW:
            self._log_gap([query], top[0][0],
                          {"kb_id": kb_id, "category": category, "module": module, "tags": tags})

        # 5. 格式化输出（含置信度反馈信号）
        output = self._format_results(top, used_reranker, queries=[query])
        return output, top

    # ============ 多查询融合检索（Agentic RAG）============

    def search_multi(self, queries, n_results=5, kb_id=None, category=None, module=None, tags=None, factory=None):
        """多查询融合检索。每个查询独立召回，跨查询 RRF 融合后统一精排。

        对比 search（单查询）：当用户用口语描述时，AI 改写出含专有名词的
        查询变体一起检索，跨越"口语→专有名词"的语义鸿沟。

        返回 (results_text, top_hits)，格式与 search 完全一致。
        """
        if warmup_busy():
            raise WarmupBusyError(
                "知识库预热中（本地降级路径冷启动约 1~3 分钟），请稍后重试；"
                "共享服务正常时不走此路径")
        self._reset_section_keys()
        where = build_where_filter(category=category, module=module, tags=tags, factory=factory)

        if kb_id:
            validate_kb_id(kb_id)
            target_kbs = [kb_id]
        else:
            target_kbs = [k for k in DEFAULT_SEARCH_KB_IDS if k in ALLOWED_KB_IDS]

        # 1. 多查询召回：每个 query 各自做混合召回
        query_hits = {}  # {query_index: [(rrf_score, doc, kb_id), ...]}
        for i, q in enumerate(queries):
            if not q or not q.strip():
                continue
            if ENABLE_HYBRID_SEARCH:
                hits = self._hybrid_recall(q, target_kbs, n_results, where)
            else:
                hits = self._vector_recall(q, target_kbs, n_results, where)
            query_hits[i] = hits

        if not query_hits:
            return "未找到相关内容", []

        # 2. 跨查询 RRF 融合
        fused = self._cross_query_fuse(query_hits)
        if not fused:
            return self._empty_recall_message()

        # 3. 规则重排（用所有 query 的分词并集做标题/h1 加权）
        rule_ranked = self._rule_rerank_multi(queries, fused)

        # 4. reranker 精排（每个 doc 用召回它的最佳 query 配对）
        rerank_pool = rule_ranked[:RERANK_POOL_K]
        reranker = get_reranker()
        if reranker is not None and len(rerank_pool) > 1:
            try:
                ranked, used_reranker = self._rerank_multi(queries, rerank_pool, reranker)
            except Exception as e:
                log(f"多查询 reranker 推理失败，降级到规则重排: {e}")
                ranked = rerank_pool
                used_reranker = False
        else:
            ranked = rerank_pool
            used_reranker = False

        # 5. MMR 去冗余（不变）
        top = self._mmr_select(ranked, n_results)

        # 命中统计（与单查询同口径：最终返回结果的唯一 source 集合）
        if top:
            record_hits({item[1].metadata.get("source", "") for item in top})

        # 低置信检索记入缺口日志
        if used_reranker and top and top[0][0] < CONFIDENCE_LOW:
            self._log_gap(queries, top[0][0],
                          {"kb_id": kb_id, "category": category, "module": module, "tags": tags})

        output = self._format_results(top, used_reranker, queries=queries)
        return output, top

    def _cross_query_fuse(self, query_hits):
        """跨查询 RRF 融合：同一 doc 被多个 query 召回则累加分数。

        query_hits: {query_index: [(rrf_score, doc, kb_id), ...]}
        每个 query 的 hits 已经是 RRF 排序的（分数降序），按位置转 rank 再做跨查询 RRF。

        返回 [(fused_score, doc, kb_id, best_query_index)]
        best_query_index 记录这个 doc 被哪个 query 排得最高（供 reranker 配对用）。
        """
        scores = {}  # {doc_key: [fused_score, doc, kb_id, best_q_idx, best_single_score]}
        for q_idx, hits in query_hits.items():
            for rank, (single_score, doc, cur_kb) in enumerate(hits):
                key = self._doc_key(doc)
                rrf = 1.0 / (RRF_K + rank)
                if key not in scores:
                    scores[key] = [0.0, doc, cur_kb, q_idx, single_score]
                scores[key][0] += rrf
                # 记录召回它的最佳 query（单查询 RRF 分最高的那个）
                if single_score > scores[key][4]:
                    scores[key][3] = q_idx
                    scores[key][4] = single_score

        result = [(s, doc, kb, bq) for s, doc, kb, bq, _ in scores.values()]
        result.sort(key=lambda x: -x[0])
        return result

    def _rule_rerank_multi(self, queries, fused):
        """规则重排（多查询版）：用所有 query 的分词并集做标题/h1/h2/tags 加权。

        比 _rule_rerank（单查询）更强的点：任一 query 的词命中标题都加分，
        覆盖面更广。同时保留跨查询 RRF 分数作为基础分。

        fused: [(fused_score, doc, kb_id, best_query_index)]
        返回: [(adj_score, doc, kb_id, best_query_index)]
        """
        # 合并所有 query 的分词
        try:
            import jieba
            all_words = set()
            for q in queries:
                words = [w for w in jieba.lcut(q.lower()) if len(w.strip()) > 1]
                all_words.update(words)
        except ImportError:
            all_words = set()
            for q in queries:
                all_words.update(w for w in q.lower().replace(",", " ").split() if len(w) > 1)

        def _rescore(item):
            score, doc, _, _ = item
            title = (doc.metadata.get("title", "") or "").lower()
            h1 = (doc.metadata.get("h1", "") or "").lower()
            h2 = (doc.metadata.get("h2", "") or "").lower()
            tag_s = (doc.metadata.get("tags", "") or "").lower()
            # 固定减分（标题最强，逐层递减）
            score -= sum(1 for w in all_words if w in title) * 0.15
            score -= sum(1 for w in all_words if w in h1) * 0.12
            score -= sum(1 for w in all_words if w in h2) * 0.10
            score -= sum(1 for w in all_words if w in tag_s) * 0.08
            # STAIR 实验（2026-09-08，均 flag 门控默认关）：
            # h3 元数据加权 + sections 章节寻址加成
            if RULE_H3_ENABLED:
                h3 = (doc.metadata.get("h3", "") or "").lower()
                score -= sum(1 for w in all_words if w in h3) * RULE_H3_WEIGHT
            if self._section_keys and (doc.metadata.get("source", ""),
                                       doc.metadata.get("h2", "")) in self._section_keys:
                score -= SECTION_BOOST
            return score

        return sorted(fused, key=_rescore)

    def _rerank_multi(self, queries, rerank_pool, reranker):
        """reranker 精排（多查询版）：每个 doc 用召回它的最佳 query 配对打分。

        doc 可能被多个 query 召回，best_query_index 记录了召回分数最高的 query。
        用该 query 与 doc 配对，让 reranker 打最准确的分。

        rerank_pool: [(score, doc, kb_id, best_query_index)]
        返回 (ranked, used_reranker)
        ranked: [(reranker_score, doc, kb_id, best_query_index)]
        """
        pairs = []
        for _, doc, _, best_q_idx in rerank_pool:
            q = queries[best_q_idx] if best_q_idx < len(queries) else queries[0]
            pairs.append((q, doc.page_content[:1000]))

        scores = reranker.predict(pairs)
        scored = list(zip(scores, rerank_pool))
        scored.sort(key=lambda x: -x[0])
        ranked = [(float(rscore), doc, kb, bq) for rscore, (_, doc, kb, bq) in scored]
        return ranked, True

    def _mmr_select(self, ranked, n_results):
        """MMR 去冗余：从排好序的候选里挑 n_results 条，保证来源多样性。

        策略：按相关性从高到低遍历，同一 source（文档）最多保留
        MMR_MAX_PER_SOURCE 条。这样 top-N 会覆盖不同文档，而不是被
        单个文档的多个章节占满。

        候选池取 ranked 的前 n_results*3 条（保证去冗余后仍能凑够 n_results）。
        若去冗余后不足 n_results（候选池里同 source 太多），回退到纯 top-N。
        """
        if MMR_MAX_PER_SOURCE <= 0:
            return ranked[:n_results]

        pool = ranked[:max(n_results * 3, n_results + 5)]
        source_count = {}
        selected = []
        for item in pool:
            doc = item[1]
            source = doc.metadata.get("source", "")
            cnt = source_count.get(source, 0)
            if cnt < MMR_MAX_PER_SOURCE:
                selected.append(item)
                source_count[source] = cnt + 1
                if len(selected) >= n_results:
                    break

        # 回退：去冗余后不足 n_results，则补纯 top-N（多样性让位于完整性）
        if len(selected) < n_results:
            selected = ranked[:n_results]
        return selected

    # ============ 召回层 ============

    def _embed_query_once(self, query):
        """查询向量化一次（embed HTTP），失败返回 None。

        向量通道整体的入口：失败时混合召回只剩 BM25 兜底，与原先
        每库各 embed 一次、逐库失败的效果一致，只是少打两条重复日志。
        """
        try:
            return get_embeddings().embed_query(query)
        except Exception as e:
            log(f"[混合检索] 查询向量化失败（向量通道跳过）: {e}")
            return None

    def _search_by_vector(self, vs, emb, k, where):
        """预计算向量的 Chroma 查询，返回 [(doc, distance)]。

        similarity_search_by_vector_with_relevance_scores 底层与
        similarity_search_with_score 同走 _results_to_docs_and_scores
        （返回原始 L2 距离，越小越相似），故结果与旧的文本查询路径逐位一致。
        """
        try:
            return vs.similarity_search_by_vector_with_relevance_scores(emb, k=k, filter=where)
        except TypeError:
            return vs.similarity_search_by_vector_with_relevance_scores(emb, k=k)

    def _query_section_keys(self, emb, target_kbs, where):
        """sections 章节级粗索引寻址（SECTION_INDEX_ENABLED 门控）：同一查询向量 +
        同一 where 查章节 collection top-K，命中节记键集合供规则重排层加成。
        通道级故障静默跳过（不产生加成，主检索不受影响）。
        混合召回与非混合降级路径共用（P3，CC 审查 20260908）。
        """
        if not SECTION_INDEX_ENABLED or emb is None:
            return
        try:
            from models import get_section_vectorstore
            for cur_kb in target_kbs:
                svs = get_section_vectorstore(cur_kb)
                for doc, _ in self._search_by_vector(svs, emb, SECTION_TOP_K, where):
                    self._section_keys.add(
                        (doc.metadata.get("source", ""), doc.metadata.get("h2", "")))
        except Exception as e:
            log(f"[sections] 章节索引查询失败（跳过加成）: {e}")

    def _vector_recall(self, query, target_kbs, n_results, where):
        """纯向量召回（降级路径）。返回 [(distance, doc, kb_id)]。

        查询向量只算一次、三库共用（原先每库各 embed 一遍同一 query，
        白付 2/3 的 embed HTTP + 推理锁开销；benchmark diff 验证结果逐位一致）。
        """
        all_hits = []
        pool_k = max(n_results * 5, 15)
        emb = self._embed_query_once(query)
        if emb is None:
            return all_hits
        for cur_kb in target_kbs:
            vs = get_vectorstore(cur_kb)
            hits = self._search_by_vector(vs, emb, pool_k, where)
            for doc, score in hits:
                all_hits.append((score, doc, cur_kb))
        self._query_section_keys(emb, target_kbs, where)
        return all_hits

    def _empty_recall_message(self):
        """零召回时的出口文案（S3③）。

        各通道全部失败（共享服务不可达等）≠ 真的没有相关知识——
        显式提示故障原因请重试，替代误导性的"未找到相关内容"。
        """
        failures = getattr(self, "_recall_failures", [])
        if failures:
            shown = "；".join(failures[:2]) + ("…" if len(failures) > 2 else "")
            return (f"⚠️ 检索通道全部失败（可能共享服务不可用），本次结果不可信，请稍后重试：\n{shown}", [])
        return "未找到相关内容", []

    def _note_recall_failure(self, reason):
        """记录一次通道失败（供 _empty_recall_message 判定零召回归因）。"""
        if not hasattr(self, "_recall_failures"):
            self._recall_failures = []
        self._recall_failures.append(str(reason))

    def _hybrid_recall(self, query, target_kbs, n_results, where):
        """混合召回：向量 + BM25，用 RRF 融合。

        流程：每库分别做向量召回(k=15) 和 BM25 召回(k=20)，
        按 RRF 公式合并两路排名，返回融合后的候选池。
        """
        self._recall_failures = []
        pool_k = max(n_results * 5, 15)
        bm25_k = max(n_results * 4, 20)

        # 查询向量只算一次、三库共用（省 2/3 embed 调用；结果向量相同，
        # benchmark diff 验证与旧的每库各 embed 路径逐位一致）
        emb = self._embed_query_once(query)
        if emb is None:
            self._note_recall_failure("向量通道：查询向量化失败（共享模型服务不可达）")

        # 收集每库的两路结果，按库做 RRF
        fused = []  # [(rrf_score, doc, kb_id)]，rrf_score 越高越相关
        for cur_kb in target_kbs:
            vec_ranked = []   # [(rank, doc)] 按向量距离升序（距离小=相似）
            bm25_ranked = []  # [(rank, doc)] 按 BM25 分降序

            # 向量召回
            if emb is not None:
                try:
                    vs = get_vectorstore(cur_kb)
                    vec_hits = self._search_by_vector(vs, emb, pool_k, where)
                    # 距离越小越相似 → rank 0 是最佳
                    vec_sorted = sorted(vec_hits, key=lambda x: x[1])
                    vec_ranked = [(i, doc) for i, (doc, _) in enumerate(vec_sorted)]
                except Exception as e:
                    self._note_recall_failure(f"向量召回失败({cur_kb}): {e}")
                    log(f"[混合检索] 向量召回失败({cur_kb}): {e}")

            # BM25 召回
            try:
                if vector_mode() == "remote":
                    # 远程模式：BM25 索引常驻共享服务（写后自动失效），直接召回。
                    # BM25 端点 503（空库/构建失败）是通道级故障，不触发远程模式回收
                    bm25_hits = bm25_query(cur_kb, query, bm25_k)
                    bm25_ranked = [(i, doc) for i, doc in enumerate(bm25_hits)]
                else:
                    bm25 = self._get_bm25(cur_kb)
                    if bm25 is not None:
                        # BM25Retriever 不支持 where 过滤，召回后在内存过滤
                        bm25_hits = bm25.invoke(query)[:bm25_k]
                        # BM25 已按相关性降序排好 → rank 0 是最佳
                        bm25_ranked = [(i, doc) for i, doc in enumerate(bm25_hits)]
                if where and bm25_ranked:
                    bm25_ranked = self._apply_meta_filter(bm25_ranked, where)
            except Exception as e:
                self._note_recall_failure(f"BM25 召回失败({cur_kb}): {e}")
                log(f"[混合检索] BM25 召回失败({cur_kb}): {e}")

            # RRF 融合：用文档文本指纹去重，合并两路排名
            fused.extend(self._rrf_fuse(vec_ranked, bm25_ranked, cur_kb))

        # 按 RRF 分数降序（分数高=被多路高频命中=更相关）
        fused.sort(key=lambda x: -x[0])

        # sections 章节寻址信号（flag 门控；与非混合降级路径共用实现）
        self._query_section_keys(emb, target_kbs, where)

        return fused

    def _get_bm25(self, kb_id):
        """获取 BM25 索引（懒加载），失败返回 None。"""
        try:
            from bm25_manager import get_bm25_retriever, is_available
            if not is_available():
                return None
            return get_bm25_retriever(kb_id)
        except Exception as e:
            log(f"[混合检索] BM25 不可用({kb_id}): {e}")
            return None

    def _doc_key(self, doc):
        """生成文档指纹用于跨通道去重（source + 内容前缀）。"""
        src = doc.metadata.get("source", "")
        content_prefix = doc.page_content[:80] if doc.page_content else ""
        return f"{src}::{content_prefix}"

    def _rrf_fuse(self, vec_ranked, bm25_ranked, cur_kb):
        """RRF（Reciprocal Rank Fusion）合并两路排名。

        RRF_score = Σ 1/(k + rank_i)，rank 从 0 开始。
        两路都命中的文档会累加两路分数（互为补充）。
        返回 [(rrf_score, doc, kb_id)]。
        """
        scores = {}  # {doc_key: [rrf_score, doc]}
        for rank, doc in vec_ranked:
            key = self._doc_key(doc)
            rrf = 1.0 / (RRF_K + rank)
            if key not in scores:
                scores[key] = [0.0, doc]
            scores[key][0] += rrf
            # 保留内容更完整的副本（向量召回的 doc 即原始）
        for rank, doc in bm25_ranked:
            key = self._doc_key(doc)
            rrf = 1.0 / (RRF_K + rank)
            if key not in scores:
                scores[key] = [0.0, doc]
            scores[key][0] += rrf

        return [(s, doc, cur_kb) for s, doc in scores.values()]

    def _apply_meta_filter(self, ranked_docs, where):
        """对 BM25 召回结果应用 metadata 过滤（BM25Retriever 不支持 where）。

        评估逻辑抽到 _match_where：支持 Chroma where 语法子集
        （字段精确匹配 / $contains 子串 / 顶层 $and、$or 组合——
        build_where_filter 的 tags 多标签"命中任一即可"用 $or 表达）。
        """
        filtered = []
        for rank, doc in ranked_docs:
            meta = doc.metadata or {}
            if self._match_where(meta, where):
                filtered.append((rank, doc))
        return filtered

    def _match_where(self, meta, where):
        """递归评估一个 where 子句对 metadata 是否命中。"""
        for k, v in where.items():
            if k in ("$and", "$or"):
                subs = v if isinstance(v, list) else [v]
                results = (self._match_where(meta, sub) for sub in subs)
                if k == "$and":
                    if not all(results):
                        return False
                else:
                    if not any(results):
                        return False
            else:
                if k not in meta:
                    return False
                if isinstance(v, dict) and "$contains" in v:
                    if v["$contains"] not in str(meta.get(k, "")):
                        return False
                elif str(meta.get(k, "")) != str(v):
                    return False
        return True

    def _rule_rerank(self, query, hits):
        """规则重排：标题/标签/h1/h2 命中关键词加权（固定减分）。"""
        query_lower = query.lower()
        # 中文用 jieba 分词（否则 "GridPanel行底色" 会被当成一个 token，
        # 永远匹配不到 title/h1 里的词）；混合英文也能正确切分
        try:
            import jieba
            raw_words = jieba.lcut(query_lower)
        except ImportError:
            raw_words = query_lower.replace(",", " ").split()
        query_words = [w.strip() for w in raw_words if len(w.strip()) > 1]

        def _rescore(item):
            score, doc, _ = item
            title = (doc.metadata.get("title", "") or "").lower()
            tag_s = (doc.metadata.get("tags", "") or "").lower()
            h1 = (doc.metadata.get("h1", "") or "").lower()
            h2 = (doc.metadata.get("h2", "") or "").lower()
            # 统计命中词数
            title_hits = sum(1 for w in query_words if w in title)
            tag_hits = sum(1 for w in query_words if w in tag_s)
            h1_hits = sum(1 for w in query_words if w in h1)
            h2_hits = sum(1 for w in query_words if w in h2)
            # 固定减分（标题最强，h1次之，标签/h2 再次）
            adj = score
            adj -= title_hits * 0.15
            adj -= h1_hits * 0.12
            adj -= h2_hits * 0.10
            adj -= tag_hits * 0.08
            # STAIR 实验（2026-09-08，均 flag 门控默认关）：
            # h3 元数据加权 + sections 章节寻址加成
            if RULE_H3_ENABLED:
                h3 = (doc.metadata.get("h3", "") or "").lower()
                adj -= sum(1 for w in query_words if w in h3) * RULE_H3_WEIGHT
            if self._section_keys and (doc.metadata.get("source", ""),
                                       doc.metadata.get("h2", "")) in self._section_keys:
                adj -= SECTION_BOOST
            return adj

        return sorted(hits, key=_rescore)

    def _format_results(self, top, used_reranker, queries=None):
        """格式化检索结果为文本。兼容 3 元组（单查询）和 4 元组（多查询）。

        输出头部带置信度判定（reranker 生效时）：高/中/低三档，
        低置信时给出可执行的重试建议（Agentic 反思信号）。
        每条结果标注生命周期状态：已废弃（status=deprecated/archived）、
        信息较旧（updated 超过 STALE_DAYS 天）。
        """
        output = []
        if top:
            output.append(self._confidence_header(top[0][0], used_reranker, queries))

        for i, item in enumerate(top, 1):
            score, doc, cur_kb = item[0], item[1], item[2]
            source = doc.metadata.get("source", "未知")
            title = doc.metadata.get("title", source)
            cat = doc.metadata.get("category", DEFAULT_CATEGORY)
            mod = doc.metadata.get("module", DEFAULT_MODULE)
            tag_s = doc.metadata.get("tags", "")
            h1 = doc.metadata.get("h1", "")
            h2 = doc.metadata.get("h2", "")
            h3 = doc.metadata.get("h3", "")

            meta_parts = [f"来源: {source}", f"库: {cur_kb}", f"分类: {cat}", f"模块: {mod}", f"工厂: {doc.metadata.get('factory', '通用')}"]
            meta_line = " | ".join(meta_parts)
            if title and title != source:
                meta_line = f"标题: {title} | {meta_line}"
            # 完整标题路径（h1>h2>h3，空层级跳过）——结构寻址信号，
            # 供 LLM 客户端精确定位/引用到章节；仅有 h1 时与标题同义，不重复展示
            heading_path = " > ".join(p for p in (h1, h2, h3) if p)
            if heading_path and (h2 or h3):
                meta_line += f" | 章节: {heading_path}"
            if tag_s:
                meta_line += f" | 标签: {tag_s}"
            updated = str(doc.metadata.get("updated", "") or "")
            if updated:
                meta_line += f" | 更新: {updated}"

            # reranker 分数越高越相关；向量距离越小越相似
            score_label = "相关性" if used_reranker else "相似度距离"
            header = f"--- 结果 {i} ({score_label} {score:.4f}){self._lifecycle_flag(doc)} ---"
            output.append(f"{header}\n{meta_line}\n内容:\n{doc.page_content}\n")

        return "\n".join(output)

    def _confidence_header(self, top1_score, used_reranker, queries):
        """检索反馈信号：置信度判定 + 低置信时的重试建议。

        阈值仅对 reranker 相关性概率有效；降级模式（距离分数）不判定。
        单查询与多查询的低置信建议不同：单查询建议改写后换 multi 重试，
        多查询建议检查变体质量/放宽过滤。
        """
        if not used_reranker:
            return "【置信度】—（reranker 不可用已降级，分数为距离，无置信度判定）"
        n_q = len([q for q in (queries or []) if q and q.strip()])
        is_single = n_q <= 1
        if top1_score >= CONFIDENCE_HIGH:
            return f"【置信度】✅ 高（top1={top1_score:.2f}）"
        if top1_score >= CONFIDENCE_LOW:
            if is_single:
                hint = "把口语查询改写为含专有名词（控件/表/存储过程名）的变体，用 search_knowledge_multi 重试"
            else:
                hint = "检查查询变体是否含正确专有名词，补充同义词变体重试"
            return (f"【置信度】⚠️ 中（top1={top1_score:.2f}）— 结果可能仅部分相关，建议核对内容；"
                    f"或{hint}")
        # 低置信：很可能没有相关知识
        if is_single:
            hint1 = "把查询改写为 2-5 个变体（口语原句+专有名词+同义词），用 search_knowledge_multi 重试"
        else:
            hint1 = "检查变体是否含正确专有名词（控件/表/存储过程名），补充同义词变体重试"
        return (
            f"【置信度】❌ 低（top1={top1_score:.2f}）— 很可能没有相关知识\n"
            f"建议：1) {hint1}\n"
            f"      2) 放宽或去掉 category/module/tags 过滤后重试\n"
            f"      3) 若确认知识缺失，可用 save_markdown 沉淀新文档补全知识库"
        )

    def _lifecycle_flag(self, doc):
        """生命周期标记：已废弃/已归档 + 信息较旧。返回 ' ⚠️xxx' 或空串。"""
        flags = []
        status = str(doc.metadata.get("status", "") or "").lower()
        if status == "deprecated":
            flags.append("⚠️已废弃（内容可能过时，存在更新版替代方案）")
        elif status == "archived":
            flags.append("⚠️已归档（仅作历史参考）")
        updated = str(doc.metadata.get("updated", "") or "")
        if updated:
            try:
                age = (datetime.date.today() - datetime.date.fromisoformat(updated)).days
                if age > STALE_DAYS:
                    flags.append(f"⏳信息较旧（更新于{updated}，已{age}天，注意核对）")
            except ValueError:
                pass
        return (" " + " ".join(flags)) if flags else ""

    def _log_gap(self, queries, top1_score, filters=None):
        """低置信检索记入缺口日志（Agentic RAG 方向四：知识库自我改进的信号源）。

        供 get_search_gaps 工具回顾：高频出现的缺口查询 → 用 save_markdown 补文档。
        进程内按查询文本去重（GAP_LOG_DEDUPE_HOURS 窗口），重试同查询不刷屏；
        改写后的变体（不同文本）会正常记录。
        """
        if not GAP_LOG_ENABLED:
            return
        try:
            qtext = [str(q) for q in (queries or []) if q and str(q).strip()]
            if not qtext:
                return
            key = "|".join(qtext)
            now = time.time()
            last = _gap_logged.get(key)
            if last is not None and (now - last) < GAP_LOG_DEDUPE_HOURS * 3600:
                return
            _gap_logged[key] = now
            entry = {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "queries": qtext,
                "top1": round(float(top1_score), 4),
                "filters": {k: v for k, v in (filters or {}).items() if v},
            }
            with open(GAP_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            log(f"缺口日志写入失败（忽略）: {e}")


# 全局单例
_retriever = None

def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = KnowledgeRetriever()
    return _retriever
