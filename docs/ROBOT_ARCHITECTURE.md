# ロボット化に向けた拡張設計

更新日: 2026-05-18

## 目標

このプロジェクトの最終形は、PC上の対話AIではなく、40cm級のタイヤ/キャタピラ式ロボットを用水路内で走らせ、掃除を続けるための「脳」と操作卓です。会話、視覚、行動判断、実機制御を混ぜると危ないため、行動系は明確に分けます。

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
  ActionPlan を作る。移動/清掃は確認つきの提案にする
        ↓
Safety Gate
  移動、接触、追従は確認や制限を必ず通す
        ↓
Actuator Adapter
  現在はDummyActuator。将来はモータ、サーボ、外部マイコン、MQTT/WebSocketなど
```

## 現在入っている境界

`src/robot/` に、将来の制御出力用の型と安全境界を追加しました。

- `WorldState`: 視界要約、危険、見えている対象、信頼度
- `RobotAction`: `say`、`look`、`move`、`stop`、`clean`、`light`、`ask_clarification`、`noop`
- `ActionPlan`: 行動列、意図、安全メモ、確認要否
- `RobotPlanner`: 観察メモと会話から、移動/清掃/停止の保守的な提案を作る
- `SafetyGate`: 緊急停止、通信、姿勢、バッテリー、視覚警告でコマンドを止める
- `DummyActuator`: 実モータの代わりに、操作状態だけ更新する
- `MissionController`: 用水路清掃ミッションの開始、一時停止、再開、完了を管理する

今はPCだけで動かす段階なので、モータ制御はまだ実行しません。かわりに、将来の実機制御が会話ループへ直接混ざらないように、Web操作卓からSafety GateとDummyActuatorを通す形にしています。

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

- Web UIにイベント履歴を時系列表示する
- `WorldState` にToF/IMU/電流センサー入力を追加する
- Safety Gateに最大連続走行時間、最大速度、清掃モータ過負荷、浸水検知を足す
- 実機前に、JSONログだけのリプレイテストを作る
- マイコン接続用の `ActuatorAdapter` をDummyActuatorから差し替え可能にする
