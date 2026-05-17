# ローカルマルチモーダル対話AI — プロジェクト仕様書（確定版）

> 作成日: 2026-04-29
> ステータス: 環境構築前 / 仕様確定フェーズ
> 想定実装者: Claude Code (Opus) によるエージェント実装

---

## 0. レビュー結果サマリ（原案からの主要変更点）

原案を技術的にレビューした上で、以下の点を確定・修正した。

| 項目 | 原案 | 確定版 | 理由 |
|---|---|---|---|
| マルチモーダルLLM | Qwen2-VL 7B / LLaVA 7B | **Qwen2.5-VL 7B-Instruct（4bit量子化）** | 後継モデルが存在し、日本語精度・画像理解ともに上位互換 |
| STT | Whisper / faster-whisper | **faster-whisper (large-v3) + Silero VAD** | CTranslate2ベースで実用速度。VADは事実上Silero一択 |
| TTS | VOICEVOX / Coqui / Style-Bert-VITS2 | **VOICEVOX（CPU側で並列実行）** | 日本語品質・低遅延・ライセンス明確。GPU資源を圧迫しない |
| 量子化 | 4bit / 8bit | **bitsandbytes 4bit (NF4)** に固定 | 16GB VRAM運用で唯一余裕が出る構成 |
| 並行処理 | 言及なし | **asyncio + キュー駆動** に確定 | 「応答中にマイク停止」を綺麗に書くため必須 |
| 設定管理 | ハードコード前提 | **`config.yaml` 集中管理** | モデル切替・ロボット移行時に必須 |
| ロギング | 言及なし | **構造化ログ + レイテンシ計測** をMVPに含める | ボトルネック特定に不可欠 |

---

## 1. プロジェクトゴール

### 1.1 最終ゴール（長期）
ラジコン型ロボットに搭載され、ユーザーを追従しながら「見ているもの」について自然に会話できる、完全ローカル動作のマルチモーダルAIエージェント。

### 1.2 MVPゴール（本仕様の対象）
PC上で以下が成立すること。

- Webカメラ映像とマイク入力をリアルタイム取得する
- ローカルLLMが「直近のカメラ映像 + ユーザー発話」を解釈する
- 音声で応答する
- 「これは何？」「あれの色は？」など、見えているものに対する質疑応答が成立する
- クラウドAPIを一切呼ばない

ロボット制御・自己位置推定・物体追跡はMVP対象外（モジュール境界だけ用意する）。

### 1.3 最小受入基準（MVP Done条件）
1. カメラに映ったものに対して「これは何？」と問うと、3回中2回以上は妥当な日本語で説明できる
2. 一連の応答（発話終了 → 音声出力開始）が**5秒以内**に完了する
3. 連続10ターンの会話で、文脈（直前の発話）を保持できる
4. VRAM使用量が常時 14GB 以下に収まる

---

## 2. ハードウェア前提

| 項目 | 仕様 |
|---|---|
| GPU | NVIDIA RTX 4060 Ti 16GB |
| OS | Windows 11（WSL2 は使用しない、ネイティブPython運用） |
| Python | 3.11.x（3.12はbitsandbytesのWindowsビルド都合で回避） |
| CUDA | 12.1（PyTorch 2.x 公式バイナリと整合） |
| カメラ | USB Webカメラ（720p以上） |
| マイク | 任意（USBマイク推奨、エコー抑制のためヘッドセット推奨） |
| スピーカー | 任意 |

---

## 3. システムアーキテクチャ

### 3.1 データフロー

```
┌──────────┐                    ┌────────────────┐
│ Camera   │──Frame(BGR)──────▶│ Frame Buffer   │
└──────────┘   1〜2 fps         │ (latest only)  │
                                └────────┬───────┘
                                         │ get_latest()
┌──────────┐  PCM 16k mono              ▼
│ Mic      │──▶ VAD ──▶ STT ──▶ ┌──────────────┐
└──────────┘  Silero  faster-w  │ Orchestrator │
                                │  (asyncio)   │
                                └──────┬───────┘
                                       │ prompt + image
                                       ▼
                                ┌──────────────┐
                                │ Qwen2.5-VL   │
                                │ 7B 4bit      │
                                └──────┬───────┘
                                       │ text
                                       ▼
                                ┌──────────────┐
                                │ VOICEVOX TTS │──▶ Speaker
                                │ ずんだもん    │
                                └──────────────┘

      ※ STT結果はWake Wordフィルタ（「じろえもん」）を通る
      ※ 全ターンは ./logs/YYYY-MM-DD.txt に追記される
```

### 3.2 並行処理モデル

- `asyncio` ベースのイベントループ1本に集約する
- 重い同期処理（LLM推論、STT、TTS合成）は `loop.run_in_executor` でスレッドプールに投げる
- ステート機械: `IDLE → WAKE_WAIT → LISTENING → THINKING → SPEAKING → IDLE`
- `SPEAKING` 中はマイク入力を破棄（バージインは将来拡張）
- `WAKE_WAIT` 中は STT 結果に **「じろえもん」** が含まれた場合のみ `LISTENING` へ遷移
- ただし `SPEAKING` 終了から `timeout_after_response_sec` 秒以内は wake word をスキップして連続会話可（自然な対話のため）

---

## 4. モジュール構成

```
ローカルモーダル/
├── PROJECT_SPEC.md          # 本ファイル
├── config.yaml              # モデル・デバイス・閾値の集中管理
├── pyproject.toml           # 依存定義（uv または pip）
├── src/
│   ├── __init__.py
│   ├── agent.py             # オーケストレータ（中核）
│   ├── config.py            # configローダ（pydantic）
│   ├── io/
│   │   ├── camera.py        # OpenCVキャプチャ + フレームバッファ
│   │   ├── mic.py           # sounddevice 入力ストリーム
│   │   └── speaker.py       # 音声再生（sounddevice / pygame）
│   ├── perception/
│   │   ├── vad.py           # Silero VAD
│   │   ├── stt.py           # faster-whisper ラッパ
│   │   └── wake_word.py     # 「じろえもん」検出（正規化＋エイリアス一致）
│   ├── reasoning/
│   │   ├── llm.py           # Qwen2.5-VL 推論ラッパ
│   │   └── memory.py        # 会話履歴 + 直近フレーム参照
│   ├── speech/
│   │   └── tts.py           # VOICEVOX HTTPクライアント
│   └── utils/
│       ├── logging.py       # 構造化ログ + 会話ログ（テキスト永続化）
│       └── metrics.py       # レイテンシ計測（ターンごと）
├── logs/                    # 会話ログ出力先（日付ごとファイル分割）
│   └── 2026-04-29.txt       # 例: 1ターン1ブロックで追記
├── tests/
│   └── ...                  # 単体テスト
└── scripts/
    ├── check_env.py         # CUDA / VRAM / デバイス確認
    └── bench_llm.py         # 推論レイテンシ計測
```

各サブパッケージは**純粋なPythonクラスとして公開**し、`agent.py` 以外はI/Oを直接持たない設計（テスト・差し替え容易）。

---

## 5. 技術スタック確定

### 5.1 モデル

| 役割 | モデル | サイズ | 備考 |
|---|---|---|---|
| Vision-Language LLM | `Qwen/Qwen2.5-VL-7B-Instruct` | 4bit NF4で約5.5GB | 画像+テキスト、日本語OK |
| STT | `faster-whisper large-v3` | 約3GB（GPU） | int8_float16 で高速化 |
| VAD | `silero-vad` (jit) | 数MB（CPU可） | 発話区間検出 |
| TTS | `VOICEVOX ENGINE` (HTTPサーバ) | CPU動作 | ローカルポート50021 |

### 5.2 主要ライブラリ

```
torch==2.4.x (cu121)
transformers>=4.45
accelerate
bitsandbytes (Windowsビルド: bitsandbytes-windows-webui or 0.43+)
faster-whisper
silero-vad
opencv-python
sounddevice
soundfile
numpy
pydantic
pyyaml
httpx                # VOICEVOX呼び出し
rich                 # ログ整形
```

### 5.3 VRAM見積もり（4bit運用時）

| コンポーネント | 想定VRAM |
|---|---|
| Qwen2.5-VL 7B (NF4) + KV cache | 6.5 〜 8.0 GB |
| faster-whisper large-v3 (int8_fp16) | 2.5 〜 3.0 GB |
| 推論時バッファ・断片化マージン | 2.0 GB |
| **合計** | **約 11 〜 13 GB** |

→ 16GB に対して 3GB 程度の余裕。許容範囲。

---

## 6. インターフェース仕様

### 6.1 `agent.py`

```python
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class Turn:
    user_text: str
    image: Optional[np.ndarray]   # BGR ndarray
    assistant_text: str
    latency_ms: dict              # {"stt": x, "llm": y, "tts": z}

class VisionAudioAgent:
    def __init__(self, config_path: str = "config.yaml") -> None: ...

    async def start(self) -> None:
        """全モジュール起動。カメラ・マイクのストリーム開始。"""

    async def stop(self) -> None:
        """グレースフルシャットダウン。"""

    async def run_forever(self) -> None:
        """発話検知→応答までを無限ループで実行。"""

    # 単発テスト用
    async def one_turn(self, user_text: str) -> Turn: ...
```

### 6.2 `config.yaml`（雛形）

```yaml
device: "cuda:0"

llm:
  model_id: "Qwen/Qwen2.5-VL-7B-Instruct"
  quantization: "nf4"
  max_new_tokens: 256
  context_window: 2048
  system_prompt: |
    あなたはカメラ映像を見ながら会話する日本語アシスタントです。
    見えているものについて、簡潔かつ正確に答えてください。

stt:
  model: "large-v3"
  compute_type: "int8_float16"
  language: "ja"

vad:
  threshold: 0.5
  min_speech_ms: 300
  min_silence_ms: 600

tts:
  endpoint: "http://127.0.0.1:50021"
  speaker_id: 3            # ずんだもん（ノーマル）

camera:
  index: 0
  width: 1280
  height: 720
  capture_fps: 2           # フレームバッファ更新頻度

memory:
  max_turns: 10

wake_word:
  enabled: true
  phrase: "じろえもん"
  # STT結果に含まれていればトリガ。表記ゆれを許容するため正規化後に部分一致。
  aliases: ["じろえもん", "ジロエモン", "次郎衛門", "じろうえもん"]
  timeout_after_response_sec: 8   # 応答後この秒数は wake word 不要で連続会話可

logging:
  level: "INFO"
  conversation_log_dir: "./logs"   # ターンごとに軽量テキストで保存
  rotate: "daily"                  # 日付ごとにファイル分割

language:
  primary: "ja"
  reject_other: true               # 日本語以外を検知したら無視 or 聞き返し

ui:
  mode: "cli"                      # CLIのみ（状態を色付きで表示）
```

---

## 7. 実装フェーズ（Claude Code 投入用タスク分解）

各フェーズは**そのフェーズだけで動作確認できる**ように切る。

### Phase 0: 環境構築
- Python 3.11 仮想環境（uv または venv）
- CUDA 12.1 / PyTorch 2.4 動作確認
- `scripts/check_env.py` で GPU・VRAM・デバイス列挙
- VOICEVOX ENGINE をローカルで起動（別プロセス）
- **Done条件**: `python -c "import torch; print(torch.cuda.is_available())"` が True

### Phase 1: LLM 単体動作
- Qwen2.5-VL 7B を 4bit でロード
- 1枚の画像 + 文字列プロンプトで推論できる
- `scripts/bench_llm.py` で推論レイテンシを計測
- **Done条件**: サンプル画像に対し日本語で説明文を返す

### Phase 2: カメラ取得
- OpenCV で指定インデックスから取得
- 最新1フレームのみ保持するスレッドセーフバッファ
- **Done条件**: `agent.see()` 相当の関数が `np.ndarray` を返す

### Phase 3: 音声入力（VAD + STT）
- sounddevice でマイクストリーム
- Silero VAD で発話区間切り出し
- faster-whisper で日本語文字起こし
- **Done条件**: マイクに話しかけると標準出力に文字列が出る

### Phase 4: TTS 出力
- VOICEVOX に HTTP で `audio_query` → `synthesis`
- WAV をそのまま再生
- **Done条件**: 任意文字列が音声として再生される

### Phase 5: 統合（オーケストレータ）
- 状態機械の実装（IDLE / WAKE_WAIT / LISTENING / THINKING / SPEAKING）
- Wake Word（「じろえもん」）検出と連続会話モード
- 会話履歴メモリ（直近Nターン）
- 会話ログを `./logs/YYYY-MM-DD.txt` に追記
- メトリクスログ出力
- **Done条件**: §1.3 の最小受入基準を満たす + 「じろえもん、これ何？」で起動・応答できる

### Phase 6: 評価・調整
- レイテンシ・VRAM計測
- プロンプトチューニング
- フレームサンプリング頻度の最適化

---

## 8. パフォーマンス目標と現実値

| 指標 | MVP目標 | 想定実測値 |
|---|---|---|
| 発話終了 → 応答音声開始 | 5秒以内 | 3.5〜5.0秒 |
| STT (3秒発話) | 1秒以内 | 0.4〜0.8秒 |
| LLM推論 (256 token, 画像1枚) | 3秒以内 | 1.5〜3.0秒 |
| TTS合成 (50字) | 1秒以内 | 0.3〜0.8秒 |
| VRAM ピーク | 14GB | 11〜13GB |

---

## 9. 主要リスクと対策

| リスク | 影響 | 対策 |
|---|---|---|
| bitsandbytes の Windows 動作不安定 | LLMロード失敗 | 代替: `auto-gptq` / `AWQ` 量子化版モデルへ切替可能にしておく |
| VRAM断片化で OOM | 長時間運用で落ちる | 定期的に `torch.cuda.empty_cache()`、KVキャッシュ上限設定 |
| マイクが応答音声を拾う（エコー） | 自分の声に反応するループ | `SPEAKING` 中はマイク完全停止、ヘッドセット推奨 |
| 画像解像度過大 | 推論時間増・VRAM圧迫 | LLM入力前に長辺 768px にリサイズ |
| 会話履歴肥大化 | コンテキスト超過 | `max_turns` で打ち切り、古い画像はサムネ化 or 破棄 |
| 光量不足での認識失敗 | 「分かりません」連発 | カメラの自動露出に任せる + プロンプトで「不明なら聞き返す」と指示 |

---

## 10. 将来拡張（ロボット化フェーズ）

MVPの**モジュール境界を保ったまま**追加できるよう設計済み。

| 機能 | 追加モジュール | 接続点 |
|---|---|---|
| 物体追跡 | `perception/tracker.py` (YOLOv8 + ByteTrack) | カメラフレームを共有 |
| 自己位置推定 | `localization/` | 独立サブシステム |
| モータ制御 | `actuation/motor.py` | エージェントから命令送信 |
| 通信 | WebSocket / MQTT | PC（脳）⇔ ラジコン（身体） |

```
PC（脳: 本MVPがそのまま動く）
   │  WebSocket
   ▼
ラジコン側マイコン（身体: モータ・センサのみ）
```

PC側は本MVPと同じプロセスで動かし、出力レイヤに「モータ命令送信」を追加するだけで拡張可能。

---

## 11. 評価指標

### 11.1 機能評価
- 物体認識の妥当性（手元の10種類の物体で評価）
- 文脈保持（10ターン会話で代名詞解決ができるか）
- 不明時の挙動（変なものを断定しないか）

### 11.2 性能評価
- ターンあたりレイテンシ p50 / p95
- VRAM 使用量推移
- 1時間連続稼働での安定性

### 11.3 ユーザビリティ評価
- 声で割り込めるか（将来拡張）
- 音声の聞き取りやすさ
- 応答の自然さ

---

## 12. 確定事項（2026-04-29 確定）

| 項目 | 確定内容 |
|---|---|
| VOICEVOX 話者 | **ずんだもん（ノーマル, speaker_id=3）** |
| ウェイクワード | **「じろえもん」**（応答後8秒間は連続会話可） |
| 会話ログ | **本ディレクトリ `./logs/` に日付ごとの軽量テキストで保存**（開発・改善に活用） |
| 対応言語 | **日本語のみ**（他言語は無視 or 聞き返し） |
| UI | **CLIのみ**（状態を色付きで表示） |

### 12.1 会話ログ仕様

- 形式: プレーンテキスト（UTF-8）、1ターン1ブロック
- パス: `./logs/YYYY-MM-DD.txt`
- 開発時に grep / tail で確認しやすい形に揃える

```
[2026-04-29 14:23:10] WAKE
[2026-04-29 14:23:12] USER : これは何？
[2026-04-29 14:23:12] IMAGE: frame_001.jpg (768x432, saved)
[2026-04-29 14:23:15] BOT  : マグカップなのだ。白くて取っ手が付いてるのだ。
[2026-04-29 14:23:15] LATENCY: stt=420ms llm=2100ms tts=380ms total=2900ms
---
```

- 画像は `./logs/frames/YYYY-MM-DD/frame_NNN.jpg` に保存（任意、`config.yaml` で ON/OFF 切替可）
- 個人情報を含む可能性があるため、`./logs/` は `.gitignore` に追加すること

### 12.2 Wake Word 検出仕様

- STT結果テキストに対して以下の処理を順に適用:
  1. ひらがな・カタカナ・漢字を含めて正規化（全角/半角・空白除去）
  2. `aliases` のいずれかに**部分一致**したら起動とみなす
  3. 一致箇所より後ろの文字列を「実際の発話内容」として LLM へ送る
- 例: 「じろえもん、これ何？」→ Wake検出 → ユーザー発話は「これ何？」

---

## 13. リファレンス

- Qwen2.5-VL: https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- Silero VAD: https://github.com/snakers4/silero-vad
- VOICEVOX ENGINE: https://github.com/VOICEVOX/voicevox_engine
- bitsandbytes: https://github.com/TimDettmers/bitsandbytes

---

**本仕様書は MVP 実装の凍結版とする。仕様変更が必要な場合は本ファイルを更新し、変更履歴を末尾に追記すること。**

## 変更履歴

| 日付 | 内容 |
|---|---|
| 2026-04-29 | 初版確定 |
| 2026-04-29 | オープン項目を確定: 声=ずんだもん / 起動語=じろえもん / 会話ログ保存 ON / 日本語のみ / CLI |
| 2026-05-17 | Gemma 4移行検討を追補。詳細は `docs/GEMMA_MIGRATION.md` に分離 |
