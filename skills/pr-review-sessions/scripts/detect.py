#!/usr/bin/env python3
"""GitHub のレビュー関連の出来事を検知して、PR セッションを起動すべきものを JSON で出す。

使い方:
  detect.py detect               検知して events を標準出力に出す（状態はまだ更新しない）
  detect.py bind THREAD SESSION  PR と立場（thread）に、Desktop のセッション ID を結び付ける
  detect.py commit ID...         処理に成功した event の ID を渡して、状態を確定する

各 event の session に、同じ PR・同じ立場で前に作ったセッションの ID が入る（なければ null）。

状態は同じフォルダの state.json に、直前の検知結果は pending.json に置く。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
PENDING = os.path.join(HERE, "pending.json")
TEST_EVENTS = os.path.join(HERE, "test_events.json")  # 動作確認用。あれば events に足し、commit で消す
INCLUDE_SELF = os.path.join(HERE, "include_self")  # 動作確認用。あれば自分のレビューも数える


def gh_json(args):
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else None


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def pr_key(repo, number):
    return f"{repo}#{number}"


def reviews_of(repo, number):
    data = gh_json(["api", "--paginate", "--slurp", f"repos/{repo}/pulls/{number}/reviews"])
    return [r for page in data or [] for r in page]


ROLE = {"request": "reviewer", "rerequest": "reviewer", "comment": "author", "approve": "author"}

FOLLOW_UP = {
    "request": "この PR のレビューを新しく依頼されました。",
    "rerequest": "この PR の再レビューを依頼されました。",
    "comment": "この PR に新しい指摘が付きました。",
    "approve": "この PR が Approve されました。",
}


def finish(event, sessions):
    """event に、セッション名、使い回すセッション、追記するメッセージを足す。"""
    role = ROLE[event["kind"]]
    thread = f"{role}:{pr_key(event['repo'], event['number'])}"
    name = f"[{event['label']}] {event['repo'].split('/', 1)[1]}#{event['number']} {event['title'][:30]}"
    event.update({
        "role": role,
        "thread": thread,
        "name": name,
        "session_title": f"⚡ {name}",
        "session": sessions.get(thread),
        "payload": f"kind={event['kind']} repo={event['repo']} pr={event['number']}",
        "message": (f"{FOLLOW_UP[event['kind']]}（kind={event['kind']} repo={event['repo']} "
                    f"pr={event['number']}）このセッションの最初の指示にある、この kind の対応を行ってください。"
                    "前回から変わった点を中心にしてください。"),
    })
    return event


def detect():
    first_run = not os.path.exists(STATE)
    state = load(STATE, {"requested": [], "reviews": {}})
    me = gh_json(["api", "user"])["login"]
    events = []

    # 1. 自分にレビューが依頼されている PR。前回の一覧になかったものが新しい依頼
    requested = gh_json(["search", "prs", "--review-requested=@me", "--state=open",
                         "--json", "repository,number,title,url", "--limit", "100"]) or []
    current_requested = []
    for pr in requested:
        repo = pr["repository"]["nameWithOwner"]
        key = pr_key(repo, pr["number"])
        current_requested.append(key)
        if key in state["requested"]:
            continue
        reviewed_before = any(r["user"] and r["user"]["login"] == me
                              for r in reviews_of(repo, pr["number"]))
        events.append({
            "id": f"req:{key}",
            "kind": "rerequest" if reviewed_before else "request",
            "label": "再レビュー" if reviewed_before else "レビュー依頼",
            "repo": repo, "number": pr["number"], "title": pr["title"], "url": pr["url"],
        })

    # 2. 自分が出した PR に、ほかの人のレビュー（Approve や指摘）が増えたか
    mine = gh_json(["search", "prs", "--author=@me", "--state=open",
                    "--json", "repository,number,title,url", "--limit", "100"]) or []
    reviews_now = {}
    for pr in mine:
        repo = pr["repository"]["nameWithOwner"]
        key = pr_key(repo, pr["number"])
        include_self = os.path.exists(INCLUDE_SELF)
        others = [r for r in reviews_of(repo, pr["number"])
                  if r["state"] != "PENDING" and r["user"]
                  and (include_self or r["user"]["login"] != me)]
        ids = sorted(r["id"] for r in others)
        reviews_now[key] = ids
        if first_run:
            continue  # 初回は既存のレビューを既読にするだけ
        seen = set(state["reviews"].get(key, []))
        new = [r for r in others if r["id"] not in seen]
        if not new:
            continue
        states = {r["state"] for r in new}
        if states & {"CHANGES_REQUESTED", "COMMENTED"}:
            kind, label = "comment", "指摘あり"
        else:
            kind, label = "approve", "Approve"
        events.append({
            "id": f"rev:{key}:{max(r['id'] for r in new)}",
            "kind": kind, "label": label,
            "repo": repo, "number": pr["number"], "title": pr["title"], "url": pr["url"],
            "reviewers": sorted({r["user"]["login"] for r in new}),
        })

    events += load(TEST_EVENTS, [])
    sessions = state.get("sessions", {})
    events = [finish(e, sessions) for e in events]

    save(PENDING, {"current_requested": current_requested,
                   "reviews_now": reviews_now, "events": events})
    print(json.dumps({"first_run": first_run, "events": events}, ensure_ascii=False, indent=2))


def bind(thread, session_id):
    state = load(STATE, {"requested": [], "reviews": {}})
    state.setdefault("sessions", {})[thread] = session_id
    save(STATE, state)
    print(json.dumps({"bound": thread, "session": session_id}, ensure_ascii=False))


def commit(ok_ids):
    state = load(STATE, {"requested": [], "reviews": {}})
    pending = load(PENDING, None)
    if pending is None:
        sys.exit("pending.json がありません。先に detect を実行してください。")
    failed = {e["id"].split(":", 1)[1].rsplit(":", 1)[0] if e["id"].startswith("rev:")
              else e["id"].split(":", 1)[1]: e for e in pending["events"] if e["id"] not in ok_ids}
    # 起動に失敗した依頼は「まだ見ていない」扱いにして、次の回にもう一度拾う
    state["requested"] = [k for k in pending["current_requested"]
                          if not (k in failed and failed[k]["id"].startswith("req:"))]
    reviews = {}
    for key, ids in pending["reviews_now"].items():
        if key in failed and failed[key]["id"].startswith("rev:"):
            reviews[key] = state["reviews"].get(key, [])
        else:
            reviews[key] = ids
    state["reviews"] = reviews
    save(STATE, state)
    os.remove(PENDING)
    if os.path.exists(TEST_EVENTS):
        os.remove(TEST_EVENTS)
    print(json.dumps({"committed": sorted(ok_ids), "retry_next_time": sorted(failed)},
                     ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "detect":
        detect()
    elif len(sys.argv) == 4 and sys.argv[1] == "bind":
        bind(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 2 and sys.argv[1] == "commit":
        commit(set(sys.argv[2:]))
    else:
        sys.exit(__doc__)
