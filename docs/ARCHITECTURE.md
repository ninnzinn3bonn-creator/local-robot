# アーキテクチャ

## 基本方針

このMVPは、PC上で「見る、聞く、考える、話す」をローカルに閉じて実行します。クラウドAPIは使いません。

設計上の優先順位は次の通りです。

- 実機デバッグしやすいこと
- モデル、マイク、カメラ、TTSを個別に差し替えられること
- 応答音声を自分で拾うループを避けること
- 将来のロボット化で、制御系を後付けできること

## データフロー

```text
Camera -> FrameBuffer -> VisionAudioAgent -> Vision Grounder -> LLM router
Mic -> VAD backend -> STT backend -> WakeWordDetector -> VisionAudioAgent
LLM router -> Chat model / Vision observation model -> VoicevoxTTS -> Speaker
VisionAudioAgent -> ConversationMemory
VisionAudioAgent -> ConversationLogger
VisionAudioAgent -> RobotPlanner -> ActionPlan
WebRuntime -> SafetyGate -> DummyActuator
WebRuntime -> MissionController
```

カメラは常に最新フレームだけを保持します。通常会話では画像をLLMへ渡さず、視覚参照がある発話だけ最新フレームを添えます。

標準構成では、通常会話は `llm.chat_model_id` に送ります。視覚参照つきのターンでは、まず `llm.vision_model_id` が観察メモを作り、最終返答は `llm.chat_model_id` が観察メモを根拠に生成します。これにより、会話品質と画像認識の責務を分離します。

## 状態機械

```text
IDLE -> WAKE_WAIT -> LISTENING -> THINKING -> SPEAKING -> WAKE_WAIT
```

| 状態 | 役割 |
|---|---|
| `IDLE` | 初期状態 |
| `WAKE_WAIT` | 発話は聞くが、Wake Wordがない発話は無視する |
| `LISTENING` | VAD/STTでユーザー発話を確定する |
| `THINKING` | LLMで応答を生成する |
| `SPEAKING` | TTS音声を再生する。マイク入力は破棄する |

応答終了から `timeout_after_response_sec` 秒以内は、Wake Wordなしで連続会話できます。

## モジュール責務

| モジュール | 責務 | 外部依存 |
|---|---|---|
| `src/agent.py` | 状態管理、I/O統合、1ターン処理 | rich, numpy |
| `src/config.py` | `config.yaml` 読み込みと型検証 | pydantic, pyyaml |
| `src/io/camera.py` | Webカメラ取得、最新フレーム保持、LLM用リサイズ | opencv-python, numpy |
| `src/io/mic.py` | マイク入力ストリームと音声チャンクキュー | sounddevice, numpy |
| `src/io/speaker.py` | WAV再生 | sounddevice, soundfile |
| `src/perception/simple_vad.py` | 軽量Energy VAD。標準構成で使う発話区間検出 | numpy |
| `src/perception/vad.py` | Silero VAD。必要時に使う高精度VAD | torch, silero-vad |
| `src/perception/stt.py` | 日本語音声文字起こし | faster-whisper |
| `src/perception/wake_word.py` | Wake Word正規化、一致、本文切り出し | 標準ライブラリ |
| `src/reasoning/llm.py` | Qwen2.5-VLロードと推論 | torch, transformers, bitsandbytes, PIL, OpenCV |
| `src/reasoning/gemma.py` | Gemma 4ロード、画像+テキスト推論、実験的ASR | torch, transformers, bitsandbytes, PIL, soundfile |
| `src/reasoning/ollama.py` | Ollama経由のチャット/視覚モデルルーティング | httpx, OpenCV |
| `src/reasoning/factory.py` | LLM backend選択 | 標準ライブラリ |
| `src/reasoning/memory.py` | 直近Nターンの会話履歴 | 標準ライブラリ |
| `src/robot/types.py` | 実機制御へ渡す `WorldState` / `ActionPlan` / `SafetyStatus` / `MissionState` 型 | 標準ライブラリ |
| `src/robot/planner.py` | 会話結果と観察メモから保守的な行動計画を作る境界 | 標準ライブラリ |
| `src/robot/safety.py` | 緊急停止、通信、姿勢、バッテリー、視覚警告を確認するSafety Gate | 標準ライブラリ |
| `src/robot/actuator.py` | 実モータ接続前のダミーActuator。操作状態だけ更新する | 標準ライブラリ |
| `src/robot/mission.py` | 用水路清掃ミッションの開始、一時停止、再開、完了状態 | 標準ライブラリ |
| `src/speech/tts.py` | VOICEVOX ENGINE HTTP呼び出し | httpx |
| `src/utils/logging.py` | richログ、会話ログ、画像ログ | rich, OpenCV |
| `src/utils/metrics.py` | レイテンシ計測 | 標準ライブラリ |

## 境界ルール

- `agent.py` が統合責務を持つ
- `vad.backend` で `energy` / `silero` を選択する
- `llm.backend` で `ollama` / `gemma` / `qwen` を選択する
- `stt.backend` で `faster-whisper` / `gemma` を選択する
- 各サブモジュールは、できるだけ小さなクラスとして独立させる
- 会話履歴には画像を保存しない。画像は最新フレームだけをLLMへ渡す
- `logs/` は個人情報を含む可能性があるためgit管理外にする
- 実モータ制御はまだ行わない。ただし `src/robot/` にSafety Gate、Mission、DummyActuatorを置き、将来の実機制御が会話ループへ直接混ざらないようにする

## まだ整理しないこと

現時点では次の大きな変更は避けます。

- `src` パッケージ名のリネーム
- 物体追跡、自己位置推定、モータ制御の実装

これらはMVPの実機通し検証が済んでから進めます。
