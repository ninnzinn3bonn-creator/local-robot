# ローカルモーダルエージェント

Webカメラ、マイク、ローカルLLM、VOICEVOXを使って、見えているものについて日本語で会話する完全ローカル動作のマルチモーダル対話AIです。

長期的にはラジコン型ロボットの「脳」として動かすことを想定しています。現在のMVPはPC上で、カメラ映像と音声入力を受け、ローカル推論で音声応答するところまでを対象にしています。

## 現在地

このPCでは、Ollama `gemma3:4b` を使う最短構成で実機起動まで確認済みです。

- 実装済み: オーケストレータ、カメラ、マイク、VAD、STT、LLM、TTS、会話メモリ、会話ログ、環境確認、LLMベンチ
- 整備済み: Python 3.11仮想環境、主要依存、VOICEVOX起動スクリプト、軽量ユニットテスト、Windows向け起動バッチ、ローカルWeb UI、実機スモーク
- 検証済み: カメラ画像のGemma3認識、VOICEVOX音声再生、マイク録音、`run.bat --one-turn`、通常常駐モードの起動停止
- 残り: ユーザーが実際にWake Wordを発話して、通常ループの音声入力認識と連続会話を実機確認する

実行時の推論経路はローカルです。Ollama、faster-whisper、VOICEVOXはいずれもこのPC上で動きます。初回セットアップやモデル取得にはネットが必要ですが、取得済みの現在構成ではネットなし起動を前提に `stt.local_files_only: true` にしています。

詳しい進捗と不足分は [docs/STATUS.md](docs/STATUS.md) を見てください。Gemma 4移行方針は [docs/GEMMA_MIGRATION.md](docs/GEMMA_MIGRATION.md) にまとめています。

## セットアップ概要

Windows 11 + Python 3.11 + RTX 4060 Ti 16GB を想定しています。現在の標準構成はOllama経由なので、PyTorch/CUDA版torchは必須ではありません。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

pip install -e ".[whisper]"
python scripts/check_env.py
```

VOICEVOX ENGINE は別プロセスで起動してください。このPCでは次のスクリプトで起動できます。

```powershell
.\scripts\start_voicevox.ps1
```

詳細手順は [docs/RUN_LOCAL.md](docs/RUN_LOCAL.md) と [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) にまとめています。

## よく使うコマンド

```powershell
# 軽量チェック（構文、pyproject、ユニットテスト）
.\.venv\Scripts\python.exe scripts\check_project.py

# 環境・デバイス確認
.\.venv\Scripts\python.exe scripts\check_env.py

# LLM単体ベンチ
.\.venv\Scripts\python.exe scripts\bench_llm.py --runs 3

# カメラ、TTS、マイク/STTの個別確認
.\.venv\Scripts\python.exe scripts\smoke_camera.py --ask
.\.venv\Scripts\python.exe scripts\smoke_tts.py
.\.venv\Scripts\python.exe scripts\smoke_mic_stt.py --seconds 5

# テキスト直入力で1ターン確認
.\.venv\Scripts\python.exe main.py --one-turn "今カメラに何が映っていますか？日本語で短く答えてください。"

# PowerShellで通常起動
.\run.bat

# ブラウザUIで起動
.\run_web.bat
```

## プロジェクト構成

```text
.
├── main.py                 # CLIエントリーポイント
├── web.py                  # Web UIエントリーポイント
├── run.bat                 # Windows用起動バッチ
├── run_web.bat             # Windows用Web UI起動バッチ
├── config.yaml             # モデル、デバイス、閾値などの設定
├── PROJECT_SPEC.md         # 詳細仕様書
├── docs/                   # 現在地、設計、環境構築、検証手順
├── scripts/                # 環境確認、ベンチ、軽量チェック
├── src/                    # アプリ本体
├── tests/                  # 軽量ユニットテスト
├── web/                    # ブラウザUI
└── logs/                   # 会話ログ出力先（git管理外）
```

モジュール境界と状態遷移は [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) に整理しています。

## ドキュメント

- [docs/STATUS.md](docs/STATUS.md): 目的に対する現在地、足りない部分、次タスク
- [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md): Windows環境構築手順
- [docs/RUN_LOCAL.md](docs/RUN_LOCAL.md): このPCでカメラ対話を起動する手順
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): 構造、状態機械、モジュール責務
- [docs/GEMMA_MIGRATION.md](docs/GEMMA_MIGRATION.md): Gemma 4への移行方針と省略できる機能
- [docs/TESTING.md](docs/TESTING.md): 検証手順とMVP受入チェック
- [PROJECT_SPEC.md](PROJECT_SPEC.md): 凍結版の詳細仕様
