#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shiftdeck 主控台的 agent 端入口 —— 等請求、回報進度、結案。

給 AI agent（Claude Code / Cursor / Codex CLI）用的三個動作：

    # 1. 等使用者在瀏覽器按下按鈕（阻塞，預設等 10 分鐘）
    python overlay/console/agent.py wait --timeout 600

    # 2. 處理途中回報進度，主控台會即時顯示給人看
    python overlay/console/agent.py status "正在重畫第 3 頁" --progress 0.4

    # 3. 處理完結案
    python overlay/console/agent.py done <request-id> --note "已換成對比頁"

`wait` 拿到請求時會順手 claim 起來（避免兩個 agent 搶同一筆），並把整筆請求以
JSON 印到 stdout，agent 直接讀那份 JSON 決定要做什麼。

**誠實的邊界**：這支腳本讓 agent「等得到」請求，但不會讓 agent 自己醒過來。
agent 必須正在跑 `wait`，或在下一輪對話主動查一次，請求才會被處理。等待期間
agent 這一輪是被佔住的——這是回合制工具的限制，不是這裡能繞過的東西。

Dependencies: 只有標準函式庫。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inbox  # noqa: E402

POLL_SECONDS = 0.5


def cmd_wait(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + args.timeout
    inbox.status_set("等待你在瀏覽器上的下一個動作", busy=False)

    while True:
        queue = inbox.pending()
        if args.kind:
            queue = [r for r in queue if r.get("kind") == args.kind]
        if queue:
            record = inbox.claim(queue[0]["id"])
            if record:
                inbox.status_set(f"收到請求：{record['kind']}",
                                 project=record.get("project"),
                                 request_id=record["id"])
                json.dump(record, sys.stdout, ensure_ascii=False, indent=2)
                sys.stdout.write("\n")
                return 0
            continue                     # 被別人搶走了，再看下一筆

        if time.monotonic() >= deadline:
            inbox.status_clear("agent 這一輪的等待已結束，請在對話框叫我一聲")
            print(json.dumps({"timeout": True, "waited": args.timeout},
                             ensure_ascii=False))
            return 2

        time.sleep(POLL_SECONDS)


def cmd_status(args: argparse.Namespace) -> int:
    payload = inbox.status_set(args.text, progress=args.progress,
                               project=args.project, request_id=args.request_id)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    record = inbox.finish(args.request_id, ok=not args.failed, note=args.note)
    if record is None:
        print(f"找不到請求 {args.request_id}", file=sys.stderr)
        return 1
    inbox.status_clear(args.note or "完成，等待下一個動作")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def cmd_peek(args: argparse.Namespace) -> int:
    """不等待，只看一眼佇列——適合每一輪對話開頭順手查。"""
    queue = inbox.pending()
    print(json.dumps({"pending": len(queue), "requests": queue},
                     ensure_ascii=False, indent=2))
    return 0 if queue else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="shiftdeck 主控台的 agent 端：等請求、回報進度、結案")
    sub = parser.add_subparsers(dest="command", required=True)

    p_wait = sub.add_parser("wait", help="阻塞等待瀏覽器送來的請求")
    p_wait.add_argument("--timeout", type=float, default=600.0, help="最多等幾秒（預設 600）")
    p_wait.add_argument("--kind", choices=inbox.KINDS, help="只等某一種請求")
    p_wait.set_defaults(func=cmd_wait)

    p_status = sub.add_parser("status", help="回報現在在做什麼")
    p_status.add_argument("text")
    p_status.add_argument("--progress", type=float, help="0 到 1 之間")
    p_status.add_argument("--project")
    p_status.add_argument("--request-id")
    p_status.set_defaults(func=cmd_status)

    p_done = sub.add_parser("done", help="把一筆請求結案")
    p_done.add_argument("request_id")
    p_done.add_argument("--note", default="")
    p_done.add_argument("--failed", action="store_true", help="標成失敗而非完成")
    p_done.set_defaults(func=cmd_done)

    p_peek = sub.add_parser("peek", help="看一眼佇列，不等待")
    p_peek.set_defaults(func=cmd_peek)

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        inbox.status_clear("agent 中止了等待")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
