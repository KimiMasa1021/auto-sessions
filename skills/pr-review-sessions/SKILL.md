---
name: pr-review-sessions
description: GitHub のレビュー依頼・再レビュー依頼、自分の PR への指摘や Approve を決まった間隔（既定は15分）で検知し、PR ごとに Claude Desktop のセッションを自動で作る仕組みを、この PC にセットアップする。「PR レビューのセッションを自動で作りたい」「GitHub のレビュー検知を入れて」「/pr-review-sessions」と言われたときに使う。設定の更新や、やめ方の案内にも使う。
---

# PR レビュー自動セッションのセットアップ

この PC に、次の仕組みを入れる。やり取りは日本語で行う。

- 親「PR レビューの検知」（スケジュール済みタスク、既定は15分ごと）が `gh` で出来事を探す。
- 出来事ごとに子「PR セッション」（ルーティン）を起動し、サイドバーに「⚡ [種類] リポジトリ#番号 件名」のセッションを作る。
- 同じ PR・同じ立場の次の出来事は、新しいセッションを作らず、最初のセッションに追記する。

| 出来事 | セッション名 |
|---|---|
| 自分がレビュアーに指定された | [レビュー依頼] |
| 自分がレビューした PR に、再びレビュー依頼が来た | [再レビュー] |
| 自分の PR に、ほかの人の COMMENTED / CHANGES_REQUESTED が付いた | [指摘あり] |
| 自分の PR に付いた新しいレビューが APPROVED だけ | [Approve] |

## このスキルのファイル

このスキルのフォルダは `${CLAUDE_SKILL_DIR}`。展開されていなければ `${CLAUDE_PLUGIN_ROOT}/skills/pr-review-sessions`、それもなければ Glob で `**/pr-review-sessions/SKILL.md` を探す。

- `scripts/detect.py`: 検知スクリプト
- `templates/parent.md`: 親のプロンプト（`{{CHILD_TRIGGER_ID}}` と `{{SKIP_KINDS}}` を置き換える）
- `templates/child.md`: 子のプロンプト（出来事ごとの対応 `{{ACT_*}}` と `{{WORKSPACE_RULE}}` を置き換える）
- `templates/actions.md`: 出来事ごとの対応の選択肢と、子への指示の文面
- 共通の手順: プラグインの `shared/setup-common.md`（このスキルのフォルダから見て `../../shared/setup-common.md`）

始める前に、共通の手順を Read で読む。

## 手順

### 1. 前提

- 共通の手順の「0. 前提を確かめる」を行う。
- Bash で `gh auth status` を実行する。
  - ログインしていなければ、`gh auth login` をユーザー自身に実行してもらって止まる（トークンを代わりに入力しない）。
  - スコープに `repo` がなければ、`gh auth refresh -s repo` を案内する。組織のリポジトリも見るなら `read:org` も要る。
- Bash で `python3 --version` を確かめる。

### 2. 検知スクリプトを置く

```bash
mkdir -p ~/.claude/pr-session-watch
cp "<このスキルのフォルダ>/scripts/detect.py" ~/.claude/pr-session-watch/detect.py
```

- すでに `~/.claude/pr-session-watch/state.json` があれば消さない。処理済みの記録とセッションの対応が入っている。
- 置いたら `python3 -I ~/.claude/pr-session-watch/detect.py detect` を一度実行し、JSON が出ることを確かめる（このあと `commit` はしない。初回の記録は親の最初の実行で行う）。

### 3. 子にさせることを聞く

人によって、出来事ごとにやりたいことが違う。`templates/actions.md` を読み、AskUserQuestion で4つの出来事を1回にまとめて聞く。

- 問いは出来事ごとに1つ（[レビュー依頼]、[再レビュー]、[指摘あり]、[Approve]）。header はそのラベルにする。
- 選択肢は actions.md の表の「選択肢」列の4つ。先頭がおすすめ（今までの動き）。各選択肢の description には、子への指示を短く言い換えて書く。
- 「Other」で書かれた文は、actions.md の決まりに従って扱う。

続けて、チェックアウトを1つでも選んだら、AskUserQuestion でリポジトリを置くフォルダを聞く（選択肢の例: `~/src`、`~/Desktop`、Other）。`~` はそのまま残してよい。

選んだ結果から、次の値を作って控える。

- ACT_REQUEST、ACT_REREQUEST、ACT_COMMENT、ACT_APPROVE: 選ばれた「子への指示」の文
- WORKSPACE_RULE: actions.md の「{{WORKSPACE_RULE}} に入れる文」
- SKIP_KINDS: 「セッションを作らない」を選んだ kind を `request, approve` のように並べたもの。なければ `なし`
- いずれも、文の中の `{{WORK_DIR}}` は聞いたフォルダに置き換える

全部を「セッションを作らない」にしたら、この仕組みを入れる意味がないことを伝えて、選び直してもらう。

### 4. 子ルーティンを作る

1. `templates/child.md` を読み、`{{ACT_REQUEST}}` `{{ACT_REREQUEST}}` `{{ACT_COMMENT}}` `{{ACT_APPROVE}}` `{{WORKSPACE_RULE}}` を 3 で作った値に置き換える。`{{` が残っていないことを確かめる。
2. 共通の手順の「1」「1.5」「2」に従う（1.5 で間隔とモデルと通知を聞く）。値は次のとおり。
   - name: `PR セッション（子）`
   - allowed_tools: `["Bash", "Read", "Glob", "Grep"]`
   - プロンプト: 1 で置き換えたもの
   - コネクタ: 要らない。作成後に `clear_mcp_connections` で外す。

### 5. 親タスクを作る

1. `templates/parent.md` を読み、`{{CHILD_TRIGGER_ID}}` を 4 で控えた trigger_id に、`{{SKIP_KINDS}}` を 3 で作った値に置き換える。
2. 置き換えたあとに `{{` が残っていないことを確かめる。
3. 共通の手順の「3」に従う。値は次のとおり。
   - taskId: `pr-session-watch`
   - title: `PR レビューの検知（親）`
   - description: `GitHub のレビュー依頼やレビューを検知し、PR ごとのセッションを作るか追記する`
   - prompt: 置き換えたもの

### 6. 伝える

共通の手順の「4」を伝える。加えて次の4点を伝える。

- 出来事ごとに選んだ対応を、一覧で示す。変えたくなったら、このスキルをもう一度実行すれば子のプロンプトだけを差し替えられる。
- 初回の実行では、自分の PR にすでに付いているレビューは記録するだけでセッションを作らない。いま来ているレビュー依頼には、初回からセッションができる。
- 子は GitHub に書き込まない。コメントやレビューの提出、push は、セッションで指示してから行う。
- セッションをアーカイブすると、その PR の次の出来事では新しいセッションができる。

## 動作確認（任意）

自分では自分の PR に依頼や Approve ができないので、試すときは次を使う。

- `~/.claude/pr-session-watch/test_events.json` に出来事の配列を書くと、次の `detect` でそれも出る（`commit` で消える）。形は `{"id", "kind", "label", "repo", "number", "title", "url"}`。kind は request / rerequest / comment / approve。
- `~/.claude/pr-session-watch/include_self` という空のファイルを置くと、自分のレビューも数える。確認が終わったら消す。

## やめるとき

共通の手順の「やめるとき」に加え、`~/.claude/pr-session-watch/` を消す。
