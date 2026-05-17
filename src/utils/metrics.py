"""
utils/metrics.py — ターンごとのレイテンシ計測ユーティリティ。

使い方:
    timer = LatencyTimer()
    timer.start("stt")
    # ... STT 処理 ...
    stt_ms = timer.stop("stt")

    summary = timer.summary()   # {"stt": 420, "llm": 2100, "tts": 380}
"""
from __future__ import annotations

import time
from typing import Dict, Optional


class LatencyTimer:
    """ターン内の各フェーズのレイテンシをミリ秒単位で計測する。"""

    def __init__(self) -> None:
        self._starts: Dict[str, float] = {}
        self._results: Dict[str, int] = {}

    def start(self, key: str) -> None:
        self._starts[key] = time.perf_counter()

    def stop(self, key: str) -> int:
        """計測を終了して経過ミリ秒を返す。"""
        if key not in self._starts:
            raise KeyError(f"Timer '{key}' has not been started.")
        elapsed_ms = int((time.perf_counter() - self._starts.pop(key)) * 1000)
        self._results[key] = elapsed_ms
        return elapsed_ms

    def summary(self) -> Dict[str, int]:
        """計測済み全フェーズの辞書を返す。"""
        return dict(self._results)

    def total_ms(self) -> int:
        return sum(self._results.values())

    def reset(self) -> None:
        self._starts.clear()
        self._results.clear()
