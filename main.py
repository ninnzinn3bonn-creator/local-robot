"""
main.py — ローカルモーダルエージェント エントリーポイント。

使い方:
  python main.py                    # デフォルト config.yaml で起動
  python main.py --config my.yaml  # 設定ファイルを指定
  python main.py --one-turn "これは何？"  # 単発テスト（マイク不要）
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from src.utils.encoding import configure_utf8_stdio

configure_utf8_stdio()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ローカルマルチモーダル対話AIエージェント")
    p.add_argument(
        "--config", default="config.yaml", metavar="PATH",
        help="設定ファイルパス（デフォルト: config.yaml）"
    )
    p.add_argument(
        "--one-turn", metavar="TEXT",
        help="テキストを直接入力して1ターンだけ実行して終了する（動作確認用）"
    )
    return p.parse_args()


async def run_one_turn(config_path: str, text: str) -> None:
    from src.agent import VisionAudioAgent

    agent = VisionAudioAgent(config_path)
    try:
        await agent.start_one_turn()
        turn = await agent.one_turn(text)
        print(f"\nUSER : {turn.user_text}")
        print(f"BOT  : {turn.assistant_text}")
        print(f"遅延 : {turn.latency_ms}")
    finally:
        await agent.stop()


async def run_forever(config_path: str) -> None:
    from src.agent import VisionAudioAgent

    agent = VisionAudioAgent(config_path)
    await agent.run_forever()


def main() -> None:
    args = parse_args()

    try:
        if args.one_turn:
            asyncio.run(run_one_turn(args.config, args.one_turn))
        else:
            asyncio.run(run_forever(args.config))
    except KeyboardInterrupt:
        print("\n停止しました。")
        sys.exit(0)


if __name__ == "__main__":
    main()
