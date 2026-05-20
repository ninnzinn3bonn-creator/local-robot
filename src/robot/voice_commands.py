"""Natural-language operator command parsing for the web robot console."""
from __future__ import annotations

import re
from typing import Optional


_SEPARATORS = re.compile(r"[\s　、。,.!?！？・「」『』（）()]+")


def parse_operator_command(text: str) -> Optional[str]:
    """Map short Japanese operator utterances to safe console commands.

    This parser is intentionally conservative. It only returns commands that
    the existing DummyActuator and SafetyGate understand.
    """
    normalized = _SEPARATORS.sub("", text.casefold())
    if not normalized:
        return None

    has_cleaning = any(word in normalized for word in ("掃除", "清掃", "ブラシ"))
    if has_cleaning and any(word in normalized for word in ("止め", "停止", "オフ", "off", "やめ", "切")):
        return "clean_off"
    if has_cleaning and any(word in normalized for word in ("して", "開始", "オン", "on", "動か", "回し")):
        return "clean_on"

    if any(word in normalized for word in ("止ま", "止め", "停止", "ストップ", "一時停止")):
        return "stop"

    if any(word in normalized for word in ("ライト", "照明", "明かり")) and any(
        word in normalized for word in ("つけ", "点け", "消し", "切り替", "オン", "オフ")
    ):
        return "lights_toggle"

    if any(word in normalized for word in ("後退", "バック", "下が", "後ろに進", "後ろへ進")):
        return "reverse"

    if any(word in normalized for word in ("左旋回", "左に曲", "左へ曲", "左に向", "左へ向", "左に回", "左へ回")):
        return "turn_left"

    if any(word in normalized for word in ("右旋回", "右に曲", "右へ曲", "右に向", "右へ向", "右に回", "右へ回")):
        return "turn_right"

    forward_phrases = (
        "前進",
        "前に進",
        "前へ進",
        "前に動",
        "前へ動",
        "まっすぐ進",
        "真っ直ぐ進",
        "少し進",
        "進んで",
        "進めて",
    )
    if any(phrase in normalized for phrase in forward_phrases):
        if not any(word in normalized for word in ("話", "会話", "説明", "議論", "続きを")):
            return "forward"

    return None
