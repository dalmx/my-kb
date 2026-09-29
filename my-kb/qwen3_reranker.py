#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Qwen3-Reranker 包装类：predict(pairs) 接口兼容 sentence_transformers.CrossEncoder。

Qwen3-Reranker 是因果语言模型，旧版 sentence-transformers 不能按 CrossEncoder
加载（新版已原生支持，未来重启试验可评估直接走原生 CrossEncoder）。打分方式
（照官方 model card 的 transformers 示例）：query/doc 按官方 chat 模板拼 prompt，
取末位 token 的 "yes"/"no" logits 做二值 softmax，
score = exp(yes) / (exp(yes) + exp(no))，落在 (0,1)，与 bge-reranker 的
sigmoid 概率同语义——config.CONFIDENCE_HIGH/LOW 判定可沿用（分布需重校准）。

显存要点：全量 logits 是 batch×seq×151936（30 对 × 2048 token 就 ~19GB），
必须 num_logits_to_keep/logits_to_keep=1 只算末位。Qwen3 要求
transformers>=4.51，而 4.42 起 forward 必有这两个参数名之一，签名探测必
命中；None 分支仅为防御（真走到全量 logits 会 OOM，宁可让它炸出来）。
"""

import inspect

import torch


class Qwen3Reranker:
    # 官方模板（本地快照 model card README:146，逐字）
    PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements '
              'based on the Query and the Instruct provided. Note that the answer '
              'can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
    SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    DEFAULT_INSTRUCT = 'Given a web search query, retrieve relevant passages that answer the query'

    def __init__(self, model_name, device="cuda", max_length=2048, batch_size=32,
                 instruction=None):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.device = device
        self.max_length = max_length
        self.batch_size = batch_size
        self.instruction = instruction or self.DEFAULT_INSTRUCT

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
        load_kwargs = {"dtype": torch.float16} if device == "cuda" else {}
        self.model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs).to(device)
        self.model.eval()
        # dtype 验证（与 model_service 另两处加载路径同防护）：transformers 4.56 起
        # torch_dtype 更名为 dtype，老版本对未知 kwarg 静默忽略会导致 fp16 假生效
        actual = next(self.model.parameters()).dtype
        if device == "cuda" and actual != torch.float16:
            raise RuntimeError(f"fp16 未生效（实际 {actual}），检查 transformers 版本")

        self.token_true = self.tokenizer.convert_tokens_to_ids("yes")
        self.token_false = self.tokenizer.convert_tokens_to_ids("no")

        self._logits_to_keep_kw = None
        for name in ("num_logits_to_keep", "logits_to_keep"):
            if name in inspect.signature(self.model.forward).parameters:
                self._logits_to_keep_kw = {name: 1}
                break

    def _encode_pairs(self, pairs):
        prefix_ids = self.tokenizer(self.PREFIX, add_special_tokens=False)["input_ids"]
        suffix_ids = self.tokenizer(self.SUFFIX, add_special_tokens=False)["input_ids"]
        budget = self.max_length - len(prefix_ids) - len(suffix_ids)
        seqs = []
        for q, d in pairs:
            body = f"<Instruct>: {self.instruction}\n<Query>: {q}\n<Document>: {d}"
            ids = self.tokenizer(body, add_special_tokens=False,
                                 truncation=True, max_length=budget)["input_ids"]
            seqs.append(prefix_ids + ids + suffix_ids)
        maxlen = max(len(s) for s in seqs)
        pad_id = self.tokenizer.pad_token_id
        if pad_id is None:
            pad_id = self.tokenizer.eos_token_id
        input_ids = torch.tensor([[pad_id] * (maxlen - len(s)) + s for s in seqs],
                                 device=self.device)
        attention_mask = torch.tensor([[0] * (maxlen - len(s)) + [1] * len(s) for s in seqs],
                                      device=self.device)
        return input_ids, attention_mask

    def _score_batch(self, pairs):
        input_ids, attention_mask = self._encode_pairs(pairs)
        with torch.no_grad():
            out = self.model(input_ids=input_ids, attention_mask=attention_mask,
                             **(self._logits_to_keep_kw or {}))
        logits = out.logits[:, -1, :]  # 末位下一 token 分布（左填充下即各自真实末位）
        yes_no = torch.stack([logits[:, self.token_false], logits[:, self.token_true]], dim=1)
        return torch.softmax(yes_no, dim=1)[:, 1].tolist()

    def predict(self, pairs):
        """与 CrossEncoder.predict 同签名：[(query, doc), ...] -> [score, ...]"""
        scores = []
        for i in range(0, len(pairs), self.batch_size):
            scores.extend(self._score_batch(pairs[i:i + self.batch_size]))
        return scores
