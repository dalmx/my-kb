# -*- coding: utf-8 -*-
"""等价性验证 wrapper：强制本次评测走本地 chroma 路径（粘性 False + 永久冷却），
与远程转发模式各跑一份 benchmark 再 diff，证明向量检索上移后行为逐位保持。"""
import sys

sys.argv = ["benchmark_eval.py", "--n", "10", "--label", "local-fallback"]
import models
models._remote_vector_mode = False
models._remote_vector_fail_ts = float("inf")  # 冷却永不过期 → 全程本地路径

import benchmark_eval
benchmark_eval.main()
