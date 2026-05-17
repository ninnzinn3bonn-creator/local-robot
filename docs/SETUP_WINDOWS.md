# Windowsセットアップ

## 前提

- Windows 11
- NVIDIA RTX 4060 Ti 16GB
- Python 3.11.x
- Ollama
- USB Webカメラ
- マイク
- VOICEVOX ENGINE

Python 3.12は、一部ローカルAI系ライブラリのWindows対応で詰まりやすいため避けます。

## 1. Python 3.11を用意する

PowerShellで確認します。

```powershell
py -0p
py -3.11 --version
```

`py` が無い場合は、Python 3.11をインストールしてから再確認してください。Microsoft Storeの `python.exe` エイリアスだけが見えている状態では、このプロジェクトは起動できません。

## 2. 仮想環境を作る

```powershell
cd D:\開発\ローカルモーダル
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

PowerShellの実行ポリシーで止まる場合は、現在のユーザー範囲で許可します。

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 3. プロジェクト依存を入れる

現在の標準構成はOllamaでLLMを動かすため、PyTorchは必須ではありません。

```powershell
pip install -e ".[dev,whisper]"
```

## 4. Ollamaモデルを用意する

```powershell
ollama pull gemma3:4b
```

## 5. VOICEVOX ENGINEを起動する

```powershell
winget install --id HiroshibaKazuyuki.VOICEVOX.CPU --exact
.\scripts\start_voicevox.ps1
```

## 6. 任意: Transformers直実行を使う場合

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -e ".[transformers-gemma]"
```

bitsandbytesがWindowsで失敗する場合は、Ollama構成へ戻すのが安全です。

## 7. VOICEVOX ENGINEを確認する

VOICEVOX ENGINEを起動し、ローカルの `http://127.0.0.1:50021` で応答する状態にします。

確認:

```powershell
python -c "import httpx; print(httpx.get('http://127.0.0.1:50021/version').text)"
```

## 8. 環境確認

```powershell
python scripts/check_env.py
```

最低限、次が確認できる必要があります。

- Python 3.11.x
- Ollamaが起動し、`gemma3:4b` が存在する
- 主要ライブラリがインポート可能
- VOICEVOX ENGINE稼働中
- カメラデバイス検出
- マイクデバイス検出

## 9. 軽量チェック

```powershell
python scripts/check_project.py
```

これは重いモデルやデバイスを使わず、構文、`pyproject.toml`、軽量ユニットテストだけを確認します。

## 10. 起動

```powershell
.\run.bat
```

テキスト直入力で1ターンだけ試す場合:

```powershell
python main.py --one-turn "これは何？"
```

## トラブルシュート

### `python` が `Python` とだけ出て終わる

Microsoft StoreのPythonエイリアスを掴んでいる可能性があります。Python 3.11をインストールし、`.venv` を作ってください。

### 日本語や記号の表示で落ちる

アプリ側で標準出力をUTF-8に寄せています。古いコンソールでまだ崩れる場合は、Windows TerminalまたはPowerShell 7を使ってください。

### VOICEVOXに接続できない

VOICEVOX ENGINEが起動していない、またはポートが `50021` 以外になっています。`config.yaml` の `tts.endpoint` と合わせてください。

### カメラやマイクが見つからない

他アプリが専有していないか、Windowsのプライバシー設定でカメラ/マイクが許可されているか確認してください。
