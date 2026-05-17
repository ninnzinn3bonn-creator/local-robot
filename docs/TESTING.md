# 検証手順

## 1. 軽量チェック

重いモデルやデバイスを使わないチェックです。開発中はまずこれを通します。

```powershell
.\.venv\Scripts\python.exe scripts\check_project.py
```

内容:

- `pyproject.toml` の読み込み
- `main.py`, `src`, `scripts`, `tests` の構文チェック
- `tests/` のユニットテスト

## 2. 環境チェック

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

確認するもの:

- Pythonバージョン
- PyTorch/CUDA/GPU/VRAM
- 主要ライブラリ
- Ollamaと選択中LLM
- VOICEVOX ENGINE
- カメラ
- マイク

標準のOllama/Gemma3構成では、PyTorch未インストールは問題ありません。

## 3. コンポーネント別チェック

### LLM

```powershell
.\.venv\Scripts\python.exe scripts\bench_llm.py --runs 3
```

見るところ:

- `config.yaml` の `llm.backend` で選んだLLMがロードできる
- テキストのみ推論が返る
- ダミー画像つき推論が返る
- p50/p95が記録される

### VOICEVOX

`scripts/check_env.py` でバージョンが表示されれば疎通はOKです。音声再生は次で確認します。

```powershell
.\.venv\Scripts\python.exe scripts\smoke_tts.py
```

### カメラ、マイク、STT

`stt.backend: "gemma"` の場合は、VAD後の短い音声クリップをGemma 4へ渡してASRします。`stt.backend: "faster-whisper"` の場合は従来の faster-whisper を使います。

現在は次のスモークテストを用意しています。

```powershell
.\.venv\Scripts\python.exe scripts\smoke_camera.py --ask
.\.venv\Scripts\python.exe scripts\smoke_tts.py
.\.venv\Scripts\python.exe scripts\smoke_mic_stt.py --seconds 5
```

## 4. 統合チェック

```powershell
.\.venv\Scripts\python.exe main.py --one-turn "今カメラに何が映っていますか？日本語で短く答えてください。"
```

確認するもの:

- LLMが応答を返す
- カメラが使える場合は画像つきで推論する
- VOICEVOXで音声が再生される
- TTSエラー時もテキスト応答は確認できる

通常ループ:

```powershell
.\run.bat
```

確認する発話:

```text
ジロー、これは何？
```

Web UI:

```powershell
.\run_web.bat
```

確認するもの:

- `http://127.0.0.1:8765` で画面が開く
- 左側にカメラ映像が更新される
- 右側に状態、会話ログ、`話しかける`、`会話終了` が表示される
- `話しかける` ボタン後の次発話はWake Wordなしで処理される
- テキスト入力から送信でき、STTなしで会話とTTSを確認できる
- 応答後の連続会話残り時間がメーターで見える
- 視覚参照のない雑談では、カメラ説明に逃げない

## 5. MVP受入チェック

| チェック | 合格条件 | 記録先 |
|---|---|---|
| 物体説明 | 10種類の身近な物体で、3回中2回以上妥当 | `logs/` と手元メモ |
| レイテンシ | 発話終了から音声出力開始まで5秒以内 | `logs/YYYY-MM-DD.txt` |
| 連続会話 | 10ターンで直前文脈を保持 | `logs/YYYY-MM-DD.txt` |
| VRAM | 常時14GB以下 | `nvidia-smi` または別途ログ |
| Wake Word | 「ジロー」または「じろえもん」で起動し、非Wake発話は無視 | `logs/` |
| エコー対策 | 応答再生中に自分の声を拾わない | 実機確認 |

## 6. このPCで検証済みの結果

2026-05-17時点で、次は実行済みです。

- `scripts/check_env.py`: Python 3.11.9、Ollama `gemma3:4b`、VOICEVOX 0.25.2、カメラ index 0/4、マイク device 1 を確認
- `scripts/check_project.py`: pyproject、Python構文、ユニットテスト合格
- `scripts/smoke_camera.py --ask`: カメラ画像を保存し、Gemma3が「白い天井と照明」と説明
- `scripts/smoke_tts.py`: VOICEVOX合成と再生に成功
- `scripts/smoke_mic_stt.py --seconds 1`: マイク録音に成功。無音時のWhisper幻覚は抑制済み
- `run.bat --one-turn ...`: カメラ画像つき応答とVOICEVOX読み上げに成功
- 通常常駐モード: VAD、STT、LLM、カメラ、マイクの起動停止に成功
- Web UI: 起動、状態API、カメラJPEG、静的画面の取得を確認
- Web UIテキスト入力: 日本語入力で雑談応答し、カメラ説明に逃げないことを確認

## 7. 失敗時の切り分け順

1. `scripts/check_project.py` が通るか
2. `scripts/check_env.py` で依存とデバイスが見えるか
3. VOICEVOXの `/version` が返るか
4. `bench_llm.py` でLLMだけ動くか
5. `main.py --one-turn` で統合の半分が動くか
6. `run.bat` でマイク含む通常ループが動くか
