---
name: jira-todo-sessions
description: Jira のプロジェクトで課題が指定のステータス（既定は To Do）に入ったら、決まった間隔（既定は15分）で検知して課題ごとに Claude Desktop のセッションを自動で作る仕組みを、この PC にセットアップする。「Jira の課題でセッションを自動で作りたい」「To Do の検知を入れて」「/jira-todo-sessions」と言われたときに使う。プロジェクトの追加、設定の更新、やめ方の案内にも使う。
---

# Jira 課題自動セッションのセットアップ

この PC に、次の仕組みを入れる。やり取りは日本語で行う。

- 親「<プロジェクト> の課題の検知」（スケジュール済みタスク、既定は15分ごと）が JQL で新しい課題を探す。
- 課題ごとに子「<プロジェクト> 課題セッション」（ルーティン）を起動し、サイドバーに「⚡ <課題キー> <件名>」のセッションを作る。
- 起動した課題には目印のラベルを付け、同じ課題で二度作らない。

プロジェクトごとに親と子を1組ずつ作る。2つ目のプロジェクトを足すときも、このスキルをもう一度使う。

## このスキルのファイル

このスキルのフォルダは `${CLAUDE_SKILL_DIR}`。展開されていなければ `${CLAUDE_PLUGIN_ROOT}/skills/jira-todo-sessions`、それもなければ Glob で `**/jira-todo-sessions/SKILL.md` を探す。

- `templates/parent.md`: 親のプロンプト
- `templates/child.md`: 子のプロンプト
- `templates/actions.md`: 子にさせることの選択肢と、子への指示の文面
- 共通の手順: プラグインの `shared/setup-common.md`（このスキルのフォルダから見て `../../shared/setup-common.md`）

始める前に、共通の手順を Read で読む。

## 手順

### 1. 前提

- 共通の手順の「0. 前提を確かめる」を行う。
- Atlassian（Jira）のコネクタのツール（`getAccessibleAtlassianResources`、`searchJiraIssuesUsingJql`、`getJiraIssue`、`editJiraIssue`）が使えることを確かめる。ToolSearch で `atlassian jira` を探す。
  - なければ、https://claude.ai/customize/connectors で Atlassian のコネクタをつないでから、もう一度実行するよう伝えて止まる。

### 2. 値を決める

1. `getAccessibleAtlassianResources` でサイトの一覧を取る。
   - 1つならそれを使う。複数ならユーザーに選んでもらう。
   - サイトのホスト名（例: `example.atlassian.net`）を SITE、id を CLOUD_ID として控える。
2. AskUserQuestion で次を聞く（既定値を最初の選択肢にする）。
   - PROJECT: プロジェクトキー。分かれば `getVisibleJiraProjects` の結果から選択肢を出す。
   - STATUS: 検知するステータス名。既定は `To Do`。
   - LABEL: 目印のラベル名。既定は `claude-session`。チームの人にも見えるラベルであることを添える。
   - 子にさせること: `templates/actions.md` の表の3つ（頭出しだけ / 下書きまで / 作業の準備まで）を選択肢にし、description に子への指示を短く言い換えて書く。人によってやりたいことが違うので、Other で自由に書けることも添える。
3. 「作業の準備まで」を選んだら、AskUserQuestion でリポジトリのフォルダ（手元にクローン済みのもの）を聞く。Bash で `git -C <フォルダ> rev-parse --show-toplevel` が通ることを確かめる。通らなければ聞き直す。
4. 選んだ結果から ACTION と WORKSPACE_RULE を作って控える（`templates/actions.md` の決まりに従い、`{{REPO_DIR}}` は聞いたフォルダに置き換える）。
5. 決めた値で一度 `searchJiraIssuesUsingJql` を試し、JQL がエラーにならないことと、いま何件が対象になるかを確かめる。
   - 対象が多いと、親の初回でその数だけセッションができる（1回で最大10件）。ユーザーに件数を伝え、多すぎるなら、先に既存の課題にラベルを付けておくか、JQL に条件を足すかを相談する。

### 3. 子ルーティンを作る

1. `templates/child.md` を読み、`{{SITE}}` `{{CLOUD_ID}}` `{{PROJECT}}` `{{STATUS}}` `{{ACTION}}` `{{WORKSPACE_RULE}}` を置き換える。`{{` が残っていないことを確かめる。
2. 共通の手順の「1」「1.5」「2」に従う（1.5 で間隔とモデルと通知を聞く）。値は次のとおり。
   - name: `<PROJECT> 課題セッション（子）`
   - allowed_tools: `["Read", "Glob", "Grep", "WebSearch", "WebFetch"]`。「作業の準備まで」を選んだときだけ `"Bash"` を足す（git を使うため）
   - プロンプト: 1 で置き換えたもの
   - コネクタ: Atlassian のコネクタだけを残す。作成後の `get` で `mcp_connections` から url に `atlassian` を含むものを探し、`update` でその1つだけの配列にする。見つからなければ、claude.ai で Atlassian のコネクタがつながっているか確かめてもらう。

### 4. 親タスクを作る

1. `templates/parent.md` を読み、`{{SITE}}` `{{CLOUD_ID}}` `{{PROJECT}}` `{{STATUS}}` `{{LABEL}}` `{{CHILD_TRIGGER_ID}}` `{{CHILD_NAME}}` を置き換える。CHILD_NAME は 3 の name。`{{` が残っていないことを確かめる。
2. 共通の手順の「3」に従う。値は次のとおり。
   - taskId: `jira-todo-watch-<PROJECT を小文字にしたもの>`
   - title: `<PROJECT> の課題の検知（親）`
   - description: `Jira <PROJECT> の新しい課題を検知し、課題ごとのセッションを作る`
   - prompt: 置き換えたもの

### 5. 伝える

共通の手順の「4」を伝える。加えて次の4点を伝える。

- 選んだ「子にさせること」。変えたくなったら、このスキルをもう一度実行すれば子のプロンプトだけを差し替えられる。
- 同じ課題をもう一度セッションにしたいときは、課題からラベルを外す。次の実行で新しいセッションができる。
- 子は Jira に書き込まない。親が書き込むのは目印のラベルだけ。
- 親は Desktop 側の Atlassian コネクタを使う。権限の確認が出たら許可する。

## やめるとき

共通の手順の「やめるとき」を伝える。目印のラベルは課題に残るので、要らなければ Jira で外す。
