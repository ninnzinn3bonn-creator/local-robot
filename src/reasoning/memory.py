"""
reasoning/memory.py — 会話履歴管理（直近 N ターン）。

- ターンは (user_text, assistant_text) のペアで保持
- max_turns を超えた場合は古いターンから削除
- LLM に渡す messages リストを生成する
- 画像は最新フレームのみ agent.py が直接渡すため、memory には保持しない
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Turn:
    """1ターンの会話ペア。"""
    user_text: str
    assistant_text: str


class ConversationMemory:
    """
    直近 N ターンの会話履歴を管理する。

    使い方:
        memory = ConversationMemory(max_turns=10)
        memory.add("これは何？", "マグカップなのだ。")
        messages = memory.to_messages("次の質問は？")
        # → [{"role": "user", ...}, {"role": "assistant", ...}, {"role": "user", ...}]
    """

    def __init__(self, max_turns: int = 10) -> None:
        self._max_turns = max_turns
        self._history: deque[Turn] = deque(maxlen=max_turns)

    def add(self, user_text: str, assistant_text: str) -> None:
        """完了したターンを履歴に追加する。"""
        self._history.append(Turn(user_text=user_text, assistant_text=assistant_text))

    def to_messages(self, current_user_text: str) -> List[dict]:
        """
        直近の会話履歴 + 現在のユーザー発話を LLM 用 messages リストに変換する。

        画像は agent.py が最後のユーザーターンに別途注入するため、
        ここでは文字列コンテンツのみを返す。
        """
        messages: List[dict] = []
        for turn in self._history:
            messages.append({"role": "user", "content": turn.user_text})
            messages.append({"role": "assistant", "content": turn.assistant_text})
        messages.append({"role": "user", "content": current_user_text})
        return messages

    def clear(self) -> None:
        """会話履歴を全消去する。"""
        self._history.clear()

    @property
    def turn_count(self) -> int:
        return len(self._history)

    @property
    def max_turns(self) -> int:
        return self._max_turns
