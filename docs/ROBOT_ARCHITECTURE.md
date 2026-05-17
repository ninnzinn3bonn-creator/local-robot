# ロボット化に向けた拡張設計

更新日: 2026-05-18

## 目標

このプロジェクトの最終形は、PC上の対話AIではなく、カメラとマイクを持つロボットの「脳」です。会話、視覚、行動判断、実機制御を混ぜると危ないため、行動系は明確に分けます。

## レイヤー

```text
Perception
  Camera / Mic / VAD / STT
        ↓
Vision Grounder
  画像を見えている事実だけの観察メモにする
        ↓
Dialogue Brain
  会話モデル、人格、短期記憶。画像は直接背負わせず観察メモを使う
        ↓
World State
  見えている物、危険、対象、信頼度
        ↓
Robot Planner
  ActionPlan を作る。現時点では発話のみ
        ↓
Safety Gate
  移動、接触、追従は確認や制限を必ず通す
        ↓
Actuator Adapter
  モータ、サーボ、外部マイコン、MQTT/WebSocketなど
```

## 現在入っている境界

`src/robot/` に、将来の制御出力用の型を追加しました。

- `WorldState`: 視界要約、危険、見えている対象、信頼度
- `RobotAction`: `say`、`look`、`move`、`stop`、`ask_clarification`、`noop`
- `ActionPlan`: 行動列、意図、安全メモ、確認要否
- `RobotPlanner`: 現在は発話だけを計画し、移動は実行しない保守的な入口

今はPCだけで動かす段階なので、モータ制御はまだ実装しません。かわりに、将来の実機制御が会話ループへ直接混ざらないように境界だけ作っています。

## 視覚理解の方針

画像つきターンでは、VLMに直接「返事」を作らせません。まず視覚モデルを観察係として使い、見えている事実だけを観察メモへ落とします。その後、会話モデルは観察メモだけを根拠に返事を作ります。

```text
Frame -> qwen2.5vl:7b observation note -> gemma3:12b reply
```

この分離により、会話モデルが見えていない机、人物、充電ステーションなどを想像して話す経路を減らします。次の段階では、この観察メモを `WorldState` に接続し、物体名、位置、危険、信頼度を構造化します。

## 実機制御を足す時の順番

1. `WorldState` をVLM結果から更新する
2. LLMの通常返答とは別に、構造化された `ActionPlan` を生成する
3. `MOVE` や接触系アクションは必ず `requires_confirmation=True` にする
4. Safety Gateで速度、距離、障害物、停止条件を検査する
5. 最後にマイコンやモータドライバへ送る

## 直近の実装候補

- VLMで「移動前の注意点」を抽出して `WorldState.hazards` に入れる
- 観察メモをWeb UIとログに表示して、画像認識と会話生成を切り分ける
- Web UIに内部状態として `WorldState` と `ActionPlan` を表示する
- `STOP` だけは最優先で通す緊急停止APIを作る
- モータ実行前に、まずログ出力だけのダミーActuatorを作る
