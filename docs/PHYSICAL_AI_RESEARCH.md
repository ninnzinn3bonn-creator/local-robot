# フィジカルAI調査メモ

更新日: 2026-05-18

## いまの課題

Webカメラの画像をVLMへ一回渡して、そのまま会話返答を作るだけだと、次の問題が出ます。

- 同じような安全文句を繰り返す
- 実際には見えていない物を想像して話す
- 画像認識、会話、ロボット行動判断の責務が混ざる
- 後で実機を動かす時に、どの認識を根拠に動いたのか追えない

そのため、会話モデルに直接画像を背負わせるのではなく、画像をいったん「観察メモ」や `WorldState` に落としてから会話や行動計画に使う構造へ寄せます。

## 参考にしたオープンソース/研究

| 対象 | 見るべき点 | このプロジェクトへの取り込み方 |
|---|---|---|
| [LeRobot](https://huggingface.co/docs/lerobot/index) | 実ロボット向けに、モデル、データセット、ツール、模倣学習/RLをまとめる方向 | 将来のデータ収集、学習済みポリシー、ロボット接続の参考にする |
| [LeRobot paper](https://arxiv.org/abs/2602.22818) | 低レベルモータ通信からデータ保存、非同期推論まで統合する設計 | 会話AIと低レベル制御を混ぜず、非同期推論と実行ループを分ける |
| [OpenVLA](https://arxiv.org/abs/2406.09246) / [GitHub](https://github.com/openvla/openvla) | 視覚、言語、行動をまとめて扱うVLA。ロボット実演データで行動を出す | すぐには採用せず、将来の操作系ポリシー候補として比較対象にする |
| [Nav2](https://nav2.org/) | 環境モデル、経路計画、制御、障害物回避、Behavior Tree | 移動ロボット化した時のナビゲーション層の基準にする |
| [MoveIt 2](https://moveit.picknik.ai/main/index.html) | Manipulation、3D perception、kinematics、motion planning | 腕やサーボを付けた時の操作計画の基準にする |
| [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) | オープンセット物体検出。テキストで対象を指定できる | VLMの文章だけに頼らず、物体のbboxと信頼度を取る候補 |
| [Grounded-SAM](https://github.com/IDEA-Research/Grounded-Segment-Anything) | Grounding DINO + SAMで検出とセグメントを組み合わせる | 「何がどこにあるか」をマスク付きで `WorldState` に入れる候補 |
| [SAM 2](https://github.com/facebookresearch/sam2) | 画像/動画のpromptable segmentationと追跡 | 同じ物体をフレーム間で追い、毎回同じ説明に戻らないようにする候補 |
| [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2) | 単眼深度推定 | カメラ1台でも「近い/遠い」の粗い危険判断を足す候補 |

## 採用するアーキテクチャ

短期は、重い物体検出やSAMを入れる前に、VLMの使い方を変えます。

```text
Camera Frame
  ↓
Vision Grounder
  qwen2.5vl:7b が、見えている事実だけの観察メモを作る
  ↓
World State / Observation Note
  物体、文字、位置、危険、不明点を保存
  ↓
Dialogue Brain
  gemma3:12b が、観察メモを根拠に会話する
  ↓
Robot Planner
  ActionPlan を作る。移動/接触は確認とSafety Gateへ
```

今回、画像つきターンではこの2段構成を入れました。

1. `qwen2.5vl:7b` に画像を渡し、見えている事実だけの観察メモを作る
2. `gemma3:12b` には画像を直接渡さず、観察メモだけを渡して会話する
3. 会話モデルには、観察メモにない物体や状況を追加で想像しないように指示する
4. 観察メモをログへ出し、視覚側の誤認識と会話側の幻覚を切り分けられるようにする

## 次に入れるべきもの

| 優先 | 内容 | 理由 |
|---|---|---|
| P0 | Web UIに観察メモを表示 | 何を根拠に話しているかを人間が確認できる |
| P1 | `WorldState` に観察メモを接続 | ロボット判断の入力を会話文から分離する |
| P1 | 物体検出候補をローカル検証 | Grounding DINO系または軽量YOLO系でbbox/信頼度を取る |
| P2 | 物体追跡 | SAM 2や軽量trackerで、同じ物体を継続的に扱う |
| P2 | 深度推定 | Depth Anything V2などで近接危険を粗く判定する |

## 判断

OpenVLAやLeRobotは、最終的に実機を動かす段階では重要です。ただし現在の問題は「会話前の視覚根拠が弱い」ことなので、まずはVLA導入より前に、観察メモ、WorldState、bbox/segmentation/depthの順で足す方が良いです。
