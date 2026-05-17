# 現在地と不足タスク

更新日: 2026-05-17

## 目的

このプロジェクトのMVPは、PC上で次の体験を成立させることです。

- Webカメラで直近の映像を取得する
- マイク音声をVAD/STTで日本語テキスト化する
- ローカルのOllama `gemma3:4b` で「映像 + 発話」を解釈する
- VOICEVOXで音声応答する
- Wake Word「じろえもん」で起動し、応答後は短時間だけ連続会話できる
- クラウドAPIを呼ばず、会話ログとレイテンシをローカルに残す

## MVP受入基準への対応状況

| 受入基準 | 現状 | 次に必要なこと |
|---|---|---|
| カメラに映ったものを3回中2回以上説明できる | 基本経路は検証済み。`smoke_camera.py --ask` と `run.bat --one-turn` で天井/照明を説明できた | 代表物体10種類で3回ずつ評価する |
| 発話終了から音声出力開始まで5秒以内 | テキスト直入力の1ターンでLLM約0.9秒、TTS約2.0秒。マイク録音とSTT起動は確認済み | 実発話からの通しレイテンシをp50/p95で記録する |
| 連続10ターンで文脈保持 | 実装あり、軽量テストあり。通常常駐モードの起動停止は確認済み | 実LLMで10ターン会話テスト |
| VRAM常時14GB以下 | Ollama/Gemma3構成で起動確認済み。長時間推移は未計測 | `nvidia-smi` で長時間運用中のピークを記録する |

## 実装済み

- `VisionAudioAgent` による統合オーケストレーション
- `asyncio` + executor によるSTT/LLM/TTSの重い処理の分離
- OpenCVカメラ取得と最新フレームバッファ
- sounddeviceマイク入力
- Silero VADラッパ
- faster-whisper STTラッパ
- Qwen2.5-VL推論ラッパ
- Gemma 4推論ラッパ
- Ollama/Gemma3推論ラッパ
- LLM backend選択
- VOICEVOX HTTPクライアント
- 会話履歴メモリ
- 会話ログとレイテンシログ
- Wake Word検出と連続会話モード
- Energy VADによるPyTorch不要の標準構成
- ローカルWeb UI。左にカメラ映像、右に会話ログ、手動発話ボタン、連続会話残り時間を表示
- 軽量ユニットテスト
- 環境確認、LLMベンチ、カメラ/TTS/マイクSTTスモークスクリプト
- VOICEVOX起動補助スクリプト

## 足りていない部分

### 完了: このPCの実行環境

- Python 3.11.9の仮想環境を作成済み
- `.[whisper]` の主要依存を導入済み
- Ollama `gemma3:4b` を導入済み
- VOICEVOX CPUを導入し、`http://127.0.0.1:50021` で起動確認済み
- RTX 4060 Ti、カメラ index 0/4、マイク device 1 AT2020USB-X を検出済み
- PyTorch/CUDA版torchは標準構成では不要
- 実行時の外部通信は使わない方針。Ollama/VOICEVOXはlocalhost、faster-whisperは `local_files_only: true` でローカルキャッシュのみ使用

### P0: 実発話での通常ループ確認

- ユーザーが `.\run.bat` を起動し、マイクへ「じろえもん、これは何？」と話す
- STTがWake Wordを別表記にする場合は `wake_word.aliases` に追加する
- 応答後8秒以内のWake Wordなし連続質問を確認する
- 応答再生中に自分の声を拾わないか確認する
- `logs/YYYY-MM-DD.txt` の記録を確認する

### P1: 評価セット検証

- 代表物体10種類の評価セットを作る
- 物体ごとに3回ずつ、説明が妥当か記録する
- 実発話から音声出力開始までのp50/p95を集計する
- VRAMピークと長時間運用時の推移を記録する

### P3: 評価と調整

- 代表物体10種類の評価セット作成
- レイテンシのp50/p95集計
- VRAMピークと長時間運用時の推移確認
- プロンプトの断定抑制と聞き返し調整
- カメラ解像度、フレームサンプリング、トークン数の調整

### P4: 将来拡張の準備

- ロボット制御出力のインターフェースだけを定義
- 物体追跡やモータ制御はMVP後に別モジュールとして追加
- 通信方式はWebSocketまたはMQTTで比較検討

## 次の実行順

1. [docs/RUN_LOCAL.md](RUN_LOCAL.md) に沿って `.\run.bat` を起動する
2. マイクに「じろえもん、これは何？」と話す
3. 返答後8秒以内に「色は？」などを続けて話す
4. 認識されない場合は `.\.venv\Scripts\python.exe scripts\smoke_mic_stt.py --seconds 5` で実際の文字起こしを確認する
5. 文字起こし上のWake Word表記を `config.yaml` の `wake_word.aliases` に追加する
6. Web UIを使う場合は `.\run_web.bat` を起動し、`http://127.0.0.1:8765` を開く

## Gemma系移行タスク

| 優先 | タスク | 状態 |
|---|---|---|
| P0 | `llm.backend` でOllama/Gemma/Qwenを切替 | 実装済み、Ollama `gemma3:4b` は実機検証済み |
| P0 | Ollama `gemma3:4b` の画像+テキスト推論 | 実装済み、実機検証済み |
| P1 | Hugging Face Gemma 4 E4Bの画像+テキスト推論 | 実装済み、標準構成では未使用 |
| P1 | `stt.backend: gemma` のASR実験 | 実装済み、未実機検証 |
| P1 | Ollama Gemma3 + faster-whisper と旧Qwen構成を比較 | 未検証 |
| P2 | Gemma 4 E4B + Gemma ASRでWhisper省略可否を判断 | 未検証 |
| P2 | function callingで将来のロボット命令JSON化を検討 | 未着手 |
