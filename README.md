# auto-sessions

Jira の新しい課題や GitHub のレビューを15分ごとに検知し、Claude Desktop のサイドバーに課題・PR ごとのセッションを自動で作る仕組みです。このプラグインは、その仕組みを自分の PC に入れるためのセットアップスキルを2つ含みます。

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
- 親: Desktop のスケジュール済みタスク（15分ごと）

最後に、サイドバーの「Scheduled」から親を開き、モデルを Haiku に、作業フォルダを消えない場所に変えてください（この2つは Edit 画面からしか変えられません）。

## 構成

```
.claude-plugin/        plugin.json と marketplace.json
shared/setup-common.md 両方のスキルが使う、親と子の作り方
skills/
  jira-todo-sessions/  SKILL.md と、親・子のプロンプトの雛形
  pr-review-sessions/  SKILL.md、検知スクリプト detect.py、親・子のプロンプトの雛形
```

## やめるとき

- 親: サイドバーの「Scheduled」から削除
- 子: https://claude.ai/code/routines で削除
- GitHub 用は `~/.claude/pr-session-watch/` も削除
