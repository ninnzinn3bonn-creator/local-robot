"""
perception/wake_word.py — ウェイクワード（「じろえもん」）検出。

仕様（§12.2）:
  1. STT 結果テキストを正規化（全角/半角・空白除去）
  2. aliases のいずれかに部分一致したら起動とみなす
  3. 一致箇所より後ろの文字列を「実際の発話内容」として返す

例: 「じろえもん、これ何？」→ wake=True, content="、これ何？"
"""
from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple


def _normalize(text: str) -> str:
    """ひらがな・カタカナ・漢字を含むテキストを正規化する。"""
    # Unicode 正規化（NFKC: 全角英数→半角、互換文字展開）
    text = unicodedata.normalize("NFKC", text)
    # 空白除去
    text = re.sub(r"\s+", "", text)
    return text


def _to_hiragana(text: str) -> str:
    """カタカナをひらがなに変換する（粗い一致のため）。"""
    result = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:  # カタカナ範囲
            result.append(chr(code - 0x60))
        else:
            result.append(ch)
    return "".join(result)


def _normalize_for_match(text: str) -> str:
    return _to_hiragana(_normalize(text))


def _normalize_with_index(text: str) -> Tuple[str, List[int]]:
    """正規化後の各文字が元テキストの何文字目に由来するかを保持する。"""
    normalized_chars: list[str] = []
    index_map: list[int] = []

    for original_index, ch in enumerate(text):
        for normalized_ch in unicodedata.normalize("NFKC", ch):
            if normalized_ch.isspace():
                continue
            normalized_chars.append(_to_hiragana(normalized_ch))
            index_map.append(original_index)

    return "".join(normalized_chars), index_map


class WakeWordDetector:
    """
    ウェイクワード検出器。

    使い方:
        detector = WakeWordDetector(aliases=["じろえもん", "ジロエモン", ...])
        detected, content = detector.detect("じろえもん、これ何？")
        # detected=True, content="、これ何？"
    """

    def __init__(
        self,
        aliases: List[str],
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        # aliases を正規化してひらがな化したパターンを事前計算
        self._patterns: List[str] = [
            _normalize_for_match(a) for a in aliases
        ]
        self._raw_aliases = aliases

    def detect(self, text: str) -> Tuple[bool, str]:
        """
        テキストにウェイクワードが含まれるか検出する。

        Returns:
            (detected: bool, content: str)
            detected=True の場合、content はウェイクワード以降のテキスト。
            detected=False の場合、content は元のテキスト全体。
        """
        if not self._enabled:
            return True, text  # 無効時は常にスルー

        normalized, index_map = _normalize_with_index(text)

        for pattern in self._patterns:
            idx = normalized.find(pattern)
            if idx != -1:
                after_normalized_pos = idx + len(pattern)
                if after_normalized_pos < len(index_map):
                    after_pos = index_map[after_normalized_pos]
                else:
                    after_pos = len(text)
                content = text[after_pos:].lstrip("、。，．,. ")
                return True, content

        return False, text

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @is_enabled.setter
    def is_enabled(self, value: bool) -> None:
        self._enabled = value
