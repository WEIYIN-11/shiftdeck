#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shiftdeck 主控台 —— 在瀏覽器裡開新簡報、看專案、看 agent 在做什麼。

    python overlay/console/server.py            # 預設 127.0.0.1:5040
    python overlay/console/server.py --port 5041 --no-browser

這一頁補上原本只能在對話框做的兩件事：**發起一份新簡報**，以及**知道 AI 現在
在忙什麼**。按下「開始製作」不會直接叫醒 AI——它把請求寫進收件匣
（`overlay/console/inbox.py`），正在跑 `agent.py wait` 的 agent 會接手；沒有
agent 在跑的時候，畫面會明說「等待 agent 接手」，而不是讓你對著轉圈猜。

只綁 127.0.0.1，不對外開；上傳的材料存進 `.shiftdeck/materials/<請求 id>/`，
agent 之後會把它複製進專案的 `sources/`，原檔一律不動。

Dependencies: flask>=3.0.0（引擎已依賴，不新增第三方套件）。
"""

from __future__ import annotations

import argparse
import re
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inbox  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PROJECTS = REPO / "projects"
MATERIALS = inbox.ROOT / "materials"
STATIC = Path(__file__).resolve().parent / "static"

MAX_UPLOAD_MB = 64
SAFE_NAME = re.compile(r"[^\w一-鿿.-]+")


def _project_rows() -> list[dict]:
    """列出 projects/ 底下的專案，附上頁數與最近匯出物。"""
    rows = []
    if not PROJECTS.exists():
        return rows
    for path in sorted(PROJECTS.iterdir(), reverse=True):
        if not path.is_dir() or path.name.startswith("."):
            continue
        svgs = sorted((path / "svg_output").glob("*.svg")) if (path / "svg_output").exists() else []
        exports = sorted((path / "exports").glob("*.pptx"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        pending_regen = (path / "live_preview" / "regen_request.json").exists()
        rows.append({
            "name": path.name,
            "pages": len(svgs),
            "export": exports[0].name if exports else None,
            "export_at": (exports[0].stat().st_mtime if exports else None),
            "pending_regen": pending_regen,
        })
    return rows


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

    @app.route("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.route("/static/<path:name>")
    def static_files(name):
        return send_from_directory(STATIC, name)

    @app.route("/api/state")
    def state():
        queue = [r for r in inbox.all_requests() if r.get("state") in ("pending", "claimed")]
        return jsonify({
            "projects": _project_rows(),
            "status": inbox.status_get(),
            "queue": queue,
            "recent": inbox.all_requests()[-8:],
        })

    @app.route("/api/new-deck", methods=["POST"])
    def new_deck():
        topic = (request.form.get("topic") or "").strip()
        audience = (request.form.get("audience") or "").strip()
        pages = (request.form.get("pages") or "").strip()
        language = (request.form.get("language") or "zh-TW").strip()
        notes = (request.form.get("notes") or "").strip()

        files = [f for f in request.files.getlist("materials") if f and f.filename]
        if not topic and not files:
            return jsonify({"error": "至少要給一個主題，或上傳一份材料"}), 400

        record = inbox.create("new_deck", {
            "topic": topic, "audience": audience, "pages": pages,
            "language": language, "notes": notes, "materials": [],
        })

        saved = []
        if files:
            target = MATERIALS / record["id"]
            target.mkdir(parents=True, exist_ok=True)
            for f in files:
                name = SAFE_NAME.sub("_", Path(f.filename).name) or secure_filename(f.filename)
                dest = target / name
                f.save(dest)
                saved.append(str(dest))
            record["payload"]["materials"] = saved
            inbox._write_atomic(inbox.INBOX / f"{record['id']}.json", record)

        return jsonify({"ok": True, "request": record, "materials": saved})

    @app.route("/api/request", methods=["POST"])
    def generic_request():
        """預覽編輯器以外的動作也走同一條路（重畫、套用修改、匯出）。"""
        body = request.get_json(silent=True) or {}
        kind = body.get("kind")
        if kind not in inbox.KINDS:
            return jsonify({"error": f"不認得的請求種類：{kind}"}), 400
        record = inbox.create(kind, body.get("payload") or {}, project=body.get("project"))
        return jsonify({"ok": True, "request": record})

    @app.route("/api/cancel/<rid>", methods=["POST"])
    def cancel(rid):
        record = inbox.finish(rid, ok=False, note="使用者取消")
        if record is None:
            return jsonify({"error": "找不到這筆請求"}), 404
        return jsonify({"ok": True, "request": record})

    return app


def _free_port(start: int, tries: int = 20) -> int:
    """從 start 往上找一個能綁的埠。

    Windows 會保留一段動態埠（Hyper-V 常見），綁下去是 WinError 10013 而不是
    「已被占用」，所以這裡直接試綁而不是只看 in-use。
    """
    import socket
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(f"從 {start} 起連續 {tries} 個埠都綁不上，請用 --port 指定一個")


def main() -> int:
    parser = argparse.ArgumentParser(description="shiftdeck 主控台")
    parser.add_argument("--port", type=int, default=5045)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    port = _free_port(args.port)
    if port != args.port:
        print(f"[shiftdeck] 埠 {args.port} 綁不上，改用 {port}")
    args.port = port

    app = create_app()
    url = f"http://127.0.0.1:{args.port}"
    print(f"[shiftdeck] 主控台：{url}")
    print(f"[shiftdeck] 專案目錄：{PROJECTS}")
    print("[shiftdeck] agent 端請跑：python overlay/console/agent.py wait")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
