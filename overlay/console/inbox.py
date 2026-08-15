#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shiftdeck 主控台收件匣 —— 瀏覽器寫請求，agent 讀請求。

**這個模組解決的問題**：原本的流程裡，瀏覽器只能「選」，每次要 AI 動手都得回
對話框打一句話（「重畫這一頁」）。收件匣把那句話換成一個檔案：瀏覽器按下按鈕
就寫一筆請求，agent 用 `wait.py` 等到它，處理完回寫狀態。人不必離開瀏覽器。

**為什麼是檔案而不是 API**：agent（Claude Code / Cursor / Codex CLI）沒有常駐
行程，也不能被 HTTP 叫醒。檔案是兩邊都能碰、且重開機不會掉的最小公約數，這也
是既有 `overlay/regen/` 選取通道用的辦法，這裡沿用同一個約定。

**誠實的邊界**：收件匣只負責「傳話」。它不會讓 AI 自己動起來——agent 必須正在
跑 `wait.py`（或下一輪對話時主動查一次）才會看到請求。沒有 agent 在跑的時候，
按鈕依然寫得進請求，只是沒有人處理，主控台會顯示「等待 agent 接手」。

佇列位置：`<repo>/.shiftdeck/inbox/*.json`，一筆請求一個檔，狀態記在檔案裡。

Dependencies: 只有標準函式庫。
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / ".shiftdeck"
INBOX = ROOT / "inbox"
STATUS = ROOT / "status.json"

KINDS = ("new_deck", "regen_page", "apply_edits", "export")
PENDING, CLAIMED, DONE, FAILED = "pending", "claimed", "done", "failed"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """先寫暫存檔再 replace —— 避免 agent 讀到只寫一半的請求。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read(path: Path) -> Optional[dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def create(kind: str, payload: dict[str, Any], project: Optional[str] = None) -> dict[str, Any]:
    """瀏覽器端呼叫：放一筆請求進收件匣，回傳整筆（含 id）。"""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {', '.join(KINDS)}")
    rid = f"{_stamp()}-{kind}-{uuid.uuid4().hex[:6]}"
    record = {
        "id": rid,
        "kind": kind,
        "project": project,
        "state": PENDING,
        "created_at": _now(),
        "claimed_at": None,
        "finished_at": None,
        "note": "",
        "payload": payload,
    }
    _write_atomic(INBOX / f"{rid}.json", record)
    return record


def all_requests() -> list[dict[str, Any]]:
    if not INBOX.exists():
        return []
    out = [r for r in (_read(p) for p in sorted(INBOX.glob("*.json"))) if r]
    return out


def pending() -> list[dict[str, Any]]:
    return [r for r in all_requests() if r.get("state") == PENDING]


def get(rid: str) -> Optional[dict[str, Any]]:
    return _read(INBOX / f"{rid}.json")


def claim(rid: str) -> Optional[dict[str, Any]]:
    """agent 端呼叫：把一筆請求標成處理中，避免兩個 agent 搶同一筆。"""
    record = get(rid)
    if not record or record.get("state") != PENDING:
        return None
    record["state"] = CLAIMED
    record["claimed_at"] = _now()
    _write_atomic(INBOX / f"{rid}.json", record)
    return record


def finish(rid: str, ok: bool = True, note: str = "") -> Optional[dict[str, Any]]:
    record = get(rid)
    if not record:
        return None
    record["state"] = DONE if ok else FAILED
    record["finished_at"] = _now()
    record["note"] = note
    _write_atomic(INBOX / f"{rid}.json", record)
    return record


def status_set(text: str, *, progress: Optional[float] = None,
               project: Optional[str] = None, request_id: Optional[str] = None,
               busy: bool = True) -> dict[str, Any]:
    """agent 回報現在在做什麼；主控台輪詢這支檔案顯示給人看。

    這是「等不到就無限轉圈」的解法：只要 agent 有在動，人就看得到它在動。
    """
    payload = {
        "busy": busy,
        "text": text,
        "progress": progress,
        "project": project,
        "request_id": request_id,
        "updated_at": _now(),
    }
    _write_atomic(STATUS, payload)
    return payload


def status_get() -> dict[str, Any]:
    return _read(STATUS) or {
        "busy": False, "text": "", "progress": None,
        "project": None, "request_id": None, "updated_at": None,
    }


def status_clear(text: str = "") -> dict[str, Any]:
    return status_set(text, busy=False)


def prune(keep: int = 50) -> int:
    """只留最近的 N 筆已完成請求，避免收件匣長成垃圾場。"""
    finished = [r for r in all_requests() if r.get("state") in (DONE, FAILED)]
    stale = finished[:-keep] if len(finished) > keep else []
    for record in stale:
        (INBOX / f"{record['id']}.json").unlink(missing_ok=True)
    return len(stale)
