# 共通の手順（親タスクと子ルーティン）

Jira 用と GitHub 用のセットアップスキルが、この手順を読んで使う。仕組みは次の2つでできている。

- **親**: Claude Desktop のスケジュール済みタスク。15分ごとに出来事を探し、見つけたら子を起動する。この PC の Desktop の中にだけある。
- **子**: claude.ai のルーティン。実行先はこの PC（ブリッジ環境）。起動されるたびに、サイドバーに「⚡ <名前>」のセッションが1つできる。

## 0. 前提を確かめる

次のツールが使えることを確かめる。読み込まれていなければ ToolSearch で読み込む。1つでも見つからなければ、Claude Desktop の Code タブで実行するよう伝えて止まる。

- `RemoteTrigger`
- `mcp__scheduled-tasks__create_scheduled_task`、`mcp__scheduled-tasks__update_scheduled_task`、`mcp__scheduled-tasks__list_scheduled_tasks`

このセッションの権限モードが Auto でなければ、「Auto にしてから実行すると、親タスクも Auto で保存されます。あとから Edit 画面で変えることもできます」と一言伝える（止まらなくてよい）。

## 1. ブリッジ環境の ID を調べる

1. Skill ツールで `schedule` スキルを読み込み、「Environments」の一覧を見る。
2. `kind: bridge` の環境を探す。
   - 1つならそれを使う。
   - 複数あれば、名前を見せてどの PC かをユーザーに選んでもらう。
   - 0 なら、「Claude Desktop の設定で、この PC をルーティンの実行先（ブリッジ環境）として登録してください」と伝えて止まる。
3. 選んだ ID（`env_...`）を控える。

## 2. 子ルーティンを作る

1. RemoteTrigger の `list` で、同じ名前のルーティンがすでにあるか確かめる。
   - あれば、作り直さずに `update` で `job_config` 全体を新しい内容にする（部分更新でも `ccr` のブロックは events まで含めて全体を送る）。
2. なければ `create` で作る。body の形:

```json
{
  "name": "<子の名前>",
  "run_once_at": "<今から1年以上先の日時（UTC, RFC3339）>",
  "enabled": true,
  "job_config": {
    "ccr": {
      "environment_id": "<1 で控えた ID>",
      "session_context": {
        "model": "claude-sonnet-5-5",
        "allowed_tools": [<スキルが指定するツール>]
      },
      "events": [
        {"data": {
          "uuid": "<新しく作った小文字の v4 UUID>",
          "session_id": "",
          "type": "user",
          "parent_tool_use_id": null,
          "message": {"role": "user", "content": "<子のプロンプト>"}
        }}
      ]
    }
  }
}
```

   - `run_once_at` はダミー。子は親からの `run` でだけ動かすので、スケジュールでは動かないよう遠い将来にする。現在時刻は `date -u` で確かめる。
   - リポジトリ（`sources`）は付けない。
3. 作成直後に `get` で `mcp_connections` を見る。作成時には、そのアカウントのコネクタがすべて自動で付くことがある。
   - コネクタが要らない子なら、`update` で `{"clear_mcp_connections": true}` を送る。
   - 特定のコネクタだけ要る子なら、`update` で `mcp_connections` をその1つだけの配列にする。
4. `trigger_id`（`trig_...`）を控える。

## 3. 親タスクを作る

1. `list_scheduled_tasks` で、同じ taskId のタスクがあるか確かめる。
   - あれば `update_scheduled_task` で prompt と description を差し替える。
   - なければ `create_scheduled_task` で作る:
     - `cronExpression`: `"*/15 * * * *"`（アプリの画面からは1時間が最短。15分ごとは Claude からしか作れない）
     - `notifyOnCompletion`: `false`（15分ごとに通知が来ないように）
     - `taskId`、`title`、`description`、`prompt` はスキルが指定する。
2. 結果に「Auto で保存されたか」が出るので控える。

## 4. 最後にユーザーに伝えること

次の3点を、短い箇条書きで伝える。

- サイドバーの「Scheduled」から親を開き、Edit で次を設定する:
  - モデル: Haiku（15分ごとに動くので軽いモデルで足りる）
  - 作業フォルダ: 消えない場所（ホームフォルダや Desktop など）
  - 権限モード: Auto（3 で Auto で保存されていなければ）
- 親を一度手動で実行し、権限の確認が出たら許可する。新しい出来事がなければ「〜はありません」で終わる。
- この PC がスリープしているか Desktop が閉じていると、親も子も動かない。

## やめるとき

- 親: サイドバーの「Scheduled」から止めるか削除する。
- 子: https://claude.ai/code/routines で削除する（API からは削除できない）。
