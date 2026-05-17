# モデル構成と底上げ方針

更新日: 2026-05-18

## 結論

会話が弱く感じる主因は、4B級の視覚モデルに「通常会話」「画像理解」「ロボット判断」をまとめて背負わせていたことです。標準構成は、役割ごとにモデルを分けます。

| 役割 | 標準 | 理由 |
|---|---|---|
| 通常会話 | Ollama `gemma3:12b` | 比較結果で意図確認が安定。画像を渡さない雑談・意図理解を担当 |
| 視覚観察 | Ollama `qwen2.5vl:7b` | ユーザーが「これ」「見て」「読んで」と言った時だけ、見えている事実の観察メモを作る |
| 比較候補 | Ollama `qwen3.5:9b` / `gemma3:4b` | 速度や軽量性を見たい時の比較対象 |
| STT | faster-whisper `small` / CPU / `int8` | 会話速度を優先。prompt/hotwordsで底上げする |
| STT比較候補 | faster-whisper `medium` / CPU / `int8` | 取得済み。精度寄りだが、このPCの実測では遅い |

`gemma3:4b` は軽量フォールバックとして残します。ただし、人格会話や意図理解には小さすぎる場面があるため、標準からは外します。

## 今回実施したこと

- `config.yaml` に `llm.chat_model_id` と `llm.vision_model_id` を追加
- 通常会話は `gemma3:12b`、視覚参照があるターンだけ `qwen2.5vl:7b` へルーティング
- `qwen2.5vl:7b`、`gemma3:12b`、比較用 `qwen3.5:9b` をOllamaに取得
- faster-whisper `medium` をこのPCへ取得し、比較候補としてキャッシュ
- STTに `initial_prompt`、`hotwords`、`hallucination_silence_threshold` を渡すように変更
- モデル比較用に `scripts/compare_ollama_models.py` と `scripts/compare_stt_models.py` を追加
- 画像つきターンを、VLM観察メモ生成と会話生成の2段構成に変更

## 評価コマンド

LLM比較:

```powershell
.\.venv\Scripts\python.exe scripts\compare_ollama_models.py --runs 1 --vision
```

STT比較:

```powershell
.\.venv\Scripts\python.exe scripts\compare_stt_models.py --models small medium
```

このPCでは、CUDAロード自体は通るものの、実際の文字起こし時に `cublas64_12.dll` が不足してCUDA実行が失敗しました。そのため標準は壊れにくいCPU `small` のままにし、CUDA STTはCUDA/cuDNN DLL整備後の追加タスクにします。

STTモデルを追加で取得する場合:

```powershell
.\.venv\Scripts\python.exe scripts\pull_stt_model.py large-v3 --device cpu --compute-type int8
```

取得後は `stt.local_files_only: true` のまま、ネットなしでロードできます。

## 判断基準

| 項目 | 見るもの |
|---|---|
| 会話品質 | カメラ説明に逃げず、ユーザーの感情・意図へ自然に返すか |
| 視覚品質 | 物体、文字、危険物、左右前後を外さないか |
| STT品質 | Wake Word、短い日本語、指示語を落とさないか |
| レイテンシ | 発話終了から音声開始までのp50/p95 |
| VRAM | Web常駐中に16GBへ張り付かないか |

## 2026-05-17 実測メモ

一回計測なので確定評価ではありませんが、今回の標準を選ぶ材料にしました。

| 対象 | 結果 |
|---|---|
| `qwen3.5:9b` | 雑談は返るが、ロボットの確認質問プロンプトで空応答が出た |
| `qwen2.5vl:7b` | 視覚応答は速め。通常会話や確認質問は短すぎる傾向 |
| `gemma3:12b` | 意図確認と人格会話が最も安定。通常会話の標準に採用 |
| STT `small` CPU int8 | VOICEVOXサンプルで約3.5秒。Wake Wordを含めてほぼ正確 |
| STT `medium` CPU int8 | 同サンプルで約8.6秒。精度差が小さく、標準にはまだ重い |
| STT CUDA | transcribe時に `cublas64_12.dll` 不足で失敗。DLL整備後に再評価 |

## 次の改善候補

- CUDA/cuDNN DLLを整備して、`medium` または `large-v3` のGPU STTを再評価
- `large-v3` のSTT比較。精度が明確に上がり、遅延が許容範囲なら標準候補へ昇格
- 会話モデルに `gemma3:12b` を使う構成の比較。じろえもん人格との相性を見る
- ロボット制御前の構造化出力。LLM応答とは別に `ActionPlan` を作り、安全ゲートで止める
- 画像入力の頻度制御。会話ターンごとではなく、必要時だけVLMを呼ぶ現在方針を継続
- 観察メモを `WorldState` に接続し、bbox/segmentation/depthを後から足せる形にする
