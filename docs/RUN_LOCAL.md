# このPCで起動する手順

更新日: 2026-05-17

このPCでは、最短で動く構成として次を使います。

- LLM/Vision: Ollama `gemma3:4b`
- Camera: OpenCV `camera.index=0`
- STT: faster-whisper `small` / CPU int8
- VAD: 軽量Energy VAD
- TTS: VOICEVOX CPU / speaker_id=3
- Mic: `device=1` AT2020USB-X
- Wake Word: 短く認識しやすい `ジロー` を推奨。`じろえもん` や `hey jiro` も別名として拾う

2026-05-17時点で、この構成は実機確認済みです。カメラ画像のGemma3認識、VOICEVOX読み上げ、マイク録音、`run.bat --one-turn`、通常常駐モードの起動停止まで通っています。

## オフライン動作の前提

この構成の実行時通信はローカルホスト宛てです。

- LLM: `http://127.0.0.1:11434` のOllama
- TTS: `http://127.0.0.1:50021` のVOICEVOX ENGINE
- STT: このPCにキャッシュ済みの faster-whisper `small`
- カメラ/マイク/スピーカー: PCのローカルデバイス

初回のPython依存導入、`ollama pull gemma3:4b`、VOICEVOX導入、Whisperモデル取得にはネットが必要です。取得済みの現在構成では、通常実行はネットなしで動く想定です。`config.yaml` の `stt.local_files_only: true` により、STTはネットから自動取得せずローカルキャッシュだけを使います。

## 1. サービスを起動

Ollamaは既に常駐しています。VOICEVOXは次で起動します。

```powershell
.\scripts\start_voicevox.ps1
```

## 2. 環境確認

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

期待値:

- Python 3.11.x
- `opencv-python`, `sounddevice`, `soundfile`, `httpx`, `rich`, `faster-whisper` がOK
- VOICEVOX ENGINE稼働中
- カメラ index 0 が見える
- マイク device 1 AT2020USB-X が見える

PyTorch未インストールは、Ollama構成では問題ありません。

## 3. 個別スモークテスト

```powershell
.\.venv\Scripts\python.exe scripts\smoke_camera.py --ask
.\.venv\Scripts\python.exe scripts\smoke_tts.py
.\.venv\Scripts\python.exe scripts\smoke_mic_stt.py --seconds 5
```

`smoke_mic_stt.py` は録音開始後に短く話してください。例:

```text
ジロー、これはテストです
```

## 4. カメラ対話の単発確認

```powershell
.\.venv\Scripts\python.exe main.py --one-turn "今カメラに何が映っていますか？日本語で短く答えてください。"
```

ここで画像認識結果が表示され、VOICEVOXで読み上げられれば、視覚応答の基本経路はOKです。

## 5. 通常起動

PowerShell上で使う場合:

```powershell
.\run.bat
```

起動が完了したら、マイクに向かって次のように話します。

```text
ジロー、これは何？
```

応答後8秒以内はWake Wordなしで続けて質問できます。

```text
色は？
```

## 6. Web UIで起動

ブラウザで見る場合:

```powershell
.\run_web.bat
```

起動後、ブラウザで次を開きます。

```text
http://127.0.0.1:8765
```

画面左にカメラ映像、右に会話ログが表示されます。通常はWake Wordで開始できます。`話しかける` ボタンを押すと、次の発話だけWake Wordなしで会話を開始できます。応答後は、右側のメーターにWake Wordなしで続けて話せる残り秒数が表示されます。`会話終了` を押すと、その連続会話モードを手動で終えます。

Web UIの映像は `camera.capture_fps` と `web/app.js` の更新間隔で決まります。現在はカメラ取得12fps、ブラウザ更新約5.5fpsです。

音声認識が崩れる場合は、右側のテキスト入力欄から送信できます。これは同じLLM/TTS経路を使うため、音声認識の問題と会話人格の問題を切り分けるためにも使えます。

通常会話では画像をLLMへ渡しません。`これ何？`、`これ読んで`、`カメラに何が見える？` のような視覚参照がある場合だけ、最新フレームを添えて応答します。

## 調整ポイント

### マイクが違う

`scripts/check_env.py` のマイク一覧を見て、[config.yaml](../config.yaml) の `mic.device` を変更します。

### カメラが違う

`camera.index` を `0` から `4` などに変更します。

### Wake Wordが認識されない

まず `scripts/smoke_mic_stt.py --seconds 5` で実際の文字起こし結果を確認します。`ジロー` や `じろえもん` が別表記になる場合は `wake_word.aliases` に追加します。

```powershell
.\.venv\Scripts\python.exe scripts\smoke_mic_stt.py --seconds 5
```

### STTが遅い/弱い

初期値は速さ重視で `small` です。精度が足りない場合は `stt.model` を `medium` または `large-v3` に上げます。CPUでは遅くなるため、まず `medium` から試します。
