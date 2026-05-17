# ロボット化に向けた拡張設計

更新日: 2026-05-17

## 目標

このプロジェクトの最終形は、PC上の対話AIではなく、カメラとマイクを持つロボットの「脳」です。会話、視覚、行動判断、実機制御を混ぜると危ないため、行動系は明確に分けます。

## レイヤー

```text
Perception
  Camera / Mic / VAD / STT
        ↓
Dialogue Brain
  会話モデル、人格、短期記憶
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

## 実機制御を足す時の順番

1. `WorldState` をVLM結果から更新する
2. LLMの通常返答とは別に、構造化された `ActionPlan` を生成する
3. `MOVE` や接触系アクションは必ず `requires_confirmation=True` にする
4. Safety Gateで速度、距離、障害物、停止条件を検査する
5. 最後にマイコンやモータドライバへ送る

## 直近の実装候補

- VLMで「移動前の注意点」を抽出して `WorldState.hazards` に入れる
- Web UIに内部状態として `WorldState` と `ActionPlan` を表示する
- `STOP` だけは最優先で通す緊急停止APIを作る
- モータ実行前に、まずログ出力だけのダミーActuatorを作る
