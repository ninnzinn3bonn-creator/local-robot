# Gemma 4移行メモ

更新日: 2026-05-17

## 結論

MVPのLLM部分は、Qwen2.5-VL固定からGemma系へ移す価値があります。このPCでまず動かす標準構成は、Ollama `gemma3:4b` です。PyTorch、Transformers、bitsandbytesを必須にせず、画像+テキスト応答まで短時間で動かせるためです。

次の比較対象として、Hugging Faceの `google/gemma-4-E4B-it` または `google/gemma-4-E2B-it` を残します。画像、テキスト、音声入力を1つのモデルに寄せられるため、将来的に `faster-whisper` 周辺を省略できる可能性があります。

ただし、すべてを消すのはまだ早いです。常時マイク入力をGemmaへ投げると重く、Wake Word前の無関係な音声までLLM推論することになります。そのため、VAD、Wake Word、TTS、ログ、状態機械は残します。

## 公式情報ベースの要点

- Gemma 4はE2B、E4B、31B、26B A4Bの4サイズ。
- Gemma 4はテキスト、画像、動画、音声入力を扱える。
- E2B/E4Bは音声入力によるASRと音声理解に対応。
- E2B/E4Bは128K context、31B/26B A4Bは256K context。
- Google公式の推定メモリは、Q4_0でE2Bが約3.2GB、E4Bが約5GB、31Bが約17.4GB、26B A4Bが約15.6GB。
- 音声はGemma 4で1秒あたり25 tokens、最大30秒クリップ。
- Gemma 4はsystem role、function calling、structured JSONをサポートする。

## このプロジェクトでの採用方針

### 第一候補

`google/gemma-4-E4B-it`

理由:

- RTX 4060 Ti 16GBで現実的に試せるサイズ。
- 画像+テキストのMVPに十分な余裕がありそう。
- 音声入力も後から統合できる。
- 31B/26B A4Bは16GB VRAMでは余裕が薄く、長時間運用とKV cacheを考えると厳しい。

### 第二候補

`google/gemma-4-E2B-it`

理由:

- 速度と安定性を優先する場合の逃げ道。
- Wake Word後の短い応答やロボット用の軽量判断には向く。
- 画像説明品質がE4Bで足りない場合はE4Bへ戻す。

## 省略できる可能性があるもの

| 対象 | 判断 | 理由 |
|---|---|---|
| `QwenVLLM`固定 | 省略/差し替え | Gemma 4 backendで画像+テキストを扱える |
| Transformers直実行 | MVPでは省略 | Ollama `gemma3:4b` で画像+テキスト応答を先に成立させる |
| CUDA版PyTorch | MVPでは省略 | 標準構成はOllama + Energy VAD + faster-whisper CPUで動く |
| `faster-whisper` | 将来省略候補 | Gemma 4 E2B/E4BでASR可能。ただし実測が必要 |
| STT専用GPUメモリ | 将来削減候補 | Gemma ASRで済めばWhisperをロードしない |
| 複雑な履歴要約 | 当面省略 | Gemma 4は長コンテキストなので、MVPでは直近履歴で十分 |
| ロボット命令パーサ | 後で簡略化 | function calling/structured JSONを使える |

## 残すもの

| 対象 | 理由 |
|---|---|
| `MicStream` | 音声入力そのものは必要 |
| `CameraCapture` | カメラ映像取得は必要 |
| VAD | Gemmaへの不要な常時音声投入を避ける。標準はEnergy VAD、必要に応じてSilero VAD |
| Wake Word検出 | 非Wake発話に反応しないため必要 |
| `VoicevoxTTS` | Gemmaはテキスト出力なので音声応答にはTTSが必要 |
| 状態機械 | SPEAKING中のエコー抑制とデバッグに必要 |
| ログ/メトリクス | 実機調整に必要 |

## 実装ステップ

### Step 1: LLM backend差し替え

`llm.backend` を追加し、`ollama`、`qwen`、`gemma` を選べるようにする。標準はOllamaです。

```yaml
llm:
  backend: "ollama"
  model_id: "gemma3:4b"
  endpoint: "http://127.0.0.1:11434"
```

### Step 2: Gemma画像+テキスト推論

`src/reasoning/gemma.py` を追加し、Hugging Face Transformersの `AutoProcessor` と `AutoModelForMultimodalLM` でロードする。

### Step 3: Gemma ASRの実験モード

`stt.backend: "gemma"` を追加し、VADで切った30秒以内の音声をGemmaへ渡して文字起こしする。

最初は安全のため、通常応答は従来どおり「文字起こし後に画像+テキストで応答」する。1回のGemma呼び出しで `transcript` と `assistant_text` を同時に返す設計は、Wake Wordの扱いと誤起動評価が済んでから行う。

### Step 4: 実機評価

比較する構成:

| 構成 | 目的 |
|---|---|
| Ollama Gemma3 4B + faster-whisper | 現在の標準。依存を抑えて実機MVPを成立させる |
| Qwen2.5-VL + faster-whisper | 旧基準 |
| Gemma 4 E4B + faster-whisper | 画像+テキスト品質と速度比較 |
| Gemma 4 E4B + Gemma ASR | 依存削減と総レイテンシ比較 |
| Gemma 4 E2B + Gemma ASR | 軽量構成の下限確認 |

## 参照

- [Gemma 4 model overview](https://ai.google.dev/gemma/docs/core)
- [Gemma 4 audio understanding](https://ai.google.dev/gemma/docs/capabilities/audio)
- [Gemma image understanding](https://ai.google.dev/gemma/docs/capabilities/vision/image)
- [Gemma 3n overview](https://ai.google.dev/gemma/docs/gemma-3n)
- [Gemma 4 announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
