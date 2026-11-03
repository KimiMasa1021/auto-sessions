# auto-sessions

Jira の新しい課題や GitHub のレビューを決まった間隔（既定は15分）で検知し、Claude Desktop のサイドバーに課題・PR ごとのセッションを自動で作る仕組みです。このプラグインは、その仕組みを自分の PC に入れるためのセットアップスキルを2つ含みます。

| スキル | 何を入れるか |
|---|---|
| `/jira-todo-sessions` | Jira のプロジェクトで課題が To Do（変更可）に入ったら、「⚡ <課題キー> <件名>」のセッションを作る |
| `/pr-review-sessions` | レビュー依頼・再レビュー依頼・自分の PR への指摘や Approve で、「⚡ [種類] リポジトリ#番号 件名」のセッションを作る。同じ PR の次の出来事は同じセッションに追記する |

## 必要なもの

- Claude Desktop（Code タブ）と、常に起きている Mac（スリープ中や Desktop を閉じているあいだは動きません）
- その PC を、ルーティンの実行先（ブリッジ環境）として登録しておくこと
- Jira 用: claude.ai で Atlassian のコネクタをつないでおくこと
- GitHub 用: `gh` にログイン済み（`repo` スコープ。組織のリポジトリは `read:org` も）、Python 3

## 入れ方

Claude Desktop のセッションで、次を順に実行します。

```
/plugin marketplace add KimiMasa1021/auto-sessions
/plugin install auto-sessions@auto-sessions
```

入れたら、Desktop のセッション（できれば権限モード Auto）で `/pr-review-sessions` か `/jira-todo-sessions` を実行します。Claude が値を聞きながら、次のものを作ります。

- 子: claude.ai のルーティン（実行先はこの PC）
- 親: Desktop のスケジュール済みタスク（間隔はセットアップ時に選ぶ。既定は15分）

セットアップの途中で、検知の間隔、子と親のモデル、通知の有無を聞かれます。子が出来事を受けて何をするかも選べます。

| スキル | 選べること |
|---|---|
| `/pr-review-sessions` | 出来事ごと（レビュー依頼・再レビュー・指摘あり・Approve）に、頭出しを書く / コメント案や修正案まで下書きする / ブランチをチェックアウトしておく / セッションを作らない、など。自由記述も可 |
| `/jira-todo-sessions` | 頭出しだけ / 実装方針と作業の分解まで下書き / 課題キーのブランチを用意しておく。自由記述も可。検知する課題の期間（今のスプリント、すべて、最近、期間指定）と担当者（自分、自分か未アサイン、絞らない、特定の人）も選べる |

どれを選んでも、GitHub や Jira への書き込みと push は、セッションで指示するまで行いません。あとから変えたいときは、スキルをもう一度実行します。

最後に、サイドバーの「Scheduled」から親を開き、Edit で次の3つを設定してください（どれも Edit 画面からしか変えられません）。

- モデル: セットアップで選んだ親のモデル
- 作業フォルダ: 消えない場所（ホームフォルダや Desktop など）
- 権限モード: Auto（Auto で保存されていなければ）

## 更新のしかた

```
claude plugin marketplace update auto-sessions
claude plugin update auto-sessions@auto-sessions
```

実行したら Claude Desktop を再起動します。

プラグインを更新しても、すでに作った親と子のプロンプトや `detect.py` は古いままです。新しい版の動きにしたいときは、スキルをもう一度実行します。親と子は作り直さずに上書きされ、GitHub 用の処理済みの記録（`~/.claude/pr-session-watch/state.json`）も残ります。

## 構成

```
.claude-plugin/        plugin.json と marketplace.json
shared/setup-common.md 両方のスキルが使う、親と子の作り方
skills/
  jira-todo-sessions/  SKILL.md と、親・子のプロンプトの雛形、子にさせることの選択肢
  pr-review-sessions/  SKILL.md、検知スクリプト detect.py、親・子のプロンプトの雛形、出来事ごとの選択肢
```

## やめるとき

- 親: サイドバーの「Scheduled」から削除
- 子: https://claude.ai/code/routines で削除
- GitHub 用は `~/.claude/pr-session-watch/` も削除
