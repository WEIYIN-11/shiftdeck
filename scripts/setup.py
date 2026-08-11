#!/usr/bin/env python3
"""shiftdeck 安裝：取得鎖定版本的引擎，套用覆蓋層。

    python scripts/setup.py            # 完整安裝
    python scripts/setup.py --check    # 只檢查狀態，不修改
    python scripts/setup.py --overlay  # 只重新套用覆蓋層（引擎已存在時）
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "engine.lock"


def fail(msg: str) -> None:
    print(f"[錯誤] {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def load_lock() -> dict:
    if not LOCK.exists():
        fail(f"找不到 {LOCK}")
    return json.loads(LOCK.read_text(encoding="utf-8"))


def engine_dir(lock: dict) -> Path:
    return ROOT / lock["engine"]["install_path"]


def installed_commit(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    r = run(["git", "rev-parse", "HEAD"], cwd=path)
    return r.stdout.strip() if r.returncode == 0 else None


def fetch_engine(lock: dict) -> None:
    eng = lock["engine"]
    dest = engine_dir(lock)
    want = eng["commit"]

    have = installed_commit(dest)
    if have == want:
        print(f"[跳過] 引擎已是鎖定版本 {eng['tag']}")
        return
    if have:
        print(f"[警告] 引擎版本不符（現有 {have[:8]}，需要 {want[:8]}），將重新取得")
        shutil.rmtree(dest, ignore_errors=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[取得] {eng['name']} {eng['tag']} …（14,000+ 檔案，需要幾分鐘）")

    r = run(["git", "clone", "--depth", "1", "--branch", eng["tag"], eng["repo"], str(dest)])
    if r.returncode != 0:
        print("[重試] 主來源失敗，改用鏡像")
        r = run(["git", "clone", "--depth", "1", "--branch", eng["tag"], eng["mirror"], str(dest)])
        if r.returncode != 0:
            fail(f"引擎取得失敗：\n{r.stderr.strip()}")

    got = installed_commit(dest)
    if got != want:
        print(f"[警告] 取得的 commit 為 {got[:8] if got else '未知'}，"
              f"與鎖定的 {want[:8]} 不符。標籤可能已被移動。")
    print(f"[完成] 引擎就緒：{dest.relative_to(ROOT)}")


def apply_overlay(lock: dict) -> None:
    """把 overlay/ 疊到引擎上。每個階段的產出在這裡註冊。"""
    dest = engine_dir(lock)
    if not dest.exists():
        fail("引擎尚未安裝，請先執行 python scripts/setup.py")

    applied = 0

    # 階段 1：繁體中文字典
    i18n = ROOT / "overlay" / "i18n" / "zh-TW"
    if any(i18n.glob("*")):
        print("[套用] 繁體中文字典 … （階段 1 完成後在此註冊實際檔案對應）")
        applied += 1

    # 階段 2：頁型庫
    pagetypes = ROOT / "overlay" / "pagetypes"
    live = [d for d in pagetypes.iterdir() if d.is_dir() and any(d.glob("*"))]
    if live:
        print(f"[套用] 頁型庫（{len(live)} 個）… （階段 2 完成後在此註冊）")
        applied += 1

    # 階段 3：動畫套組
    anims = ROOT / "overlay" / "animations"
    if any(anims.glob("*")):
        print("[套用] 動畫套組 … （階段 3 完成後在此註冊）")
        applied += 1

    # 階段 4：引擎修補（唯一破例，每個 patch 都是合併債務）
    patches = sorted((ROOT / "overlay" / "patches").glob("*.patch"))
    for p in patches:
        r = run(["git", "apply", "--check", str(p)], cwd=dest)
        if r.returncode != 0:
            fail(f"修補 {p.name} 無法套用到目前引擎版本：\n{r.stderr.strip()}")
        run(["git", "apply", str(p)], cwd=dest)
        print(f"[修補] {p.name}")
        applied += 1

    print(f"[完成] 覆蓋層套用 {applied} 項" if applied else "[提示] 覆蓋層目前為空（尚未進入階段 1）")


def install_deps(lock: dict) -> None:
    req = engine_dir(lock) / "requirements.txt"
    if not req.exists():
        print("[跳過] 找不到 requirements.txt")
        return
    print("[安裝] Python 依賴 …")
    r = run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])
    if r.returncode != 0:
        print(f"[警告] 依賴安裝未完全成功：\n{r.stderr.strip()[:400]}")
    else:
        print("[完成] 依賴就緒")


def check(lock: dict) -> None:
    eng = lock["engine"]
    dest = engine_dir(lock)
    have = installed_commit(dest)
    print(f"鎖定版本  {eng['tag']} ({eng['commit'][:8]})")
    if have is None:
        print("引擎狀態  未安裝 —— 執行 python scripts/setup.py")
    elif have == eng["commit"]:
        print("引擎狀態  就緒且版本相符")
    else:
        print(f"引擎狀態  版本不符（現有 {have[:8]}）")
    patched = lock.get("overlay_contract", {}).get("patched_files", [])
    print(f"引擎修補  {len(patched)} 個檔案" + (f"：{', '.join(patched)}" if patched else "（乾淨）"))


def main() -> None:
    ap = argparse.ArgumentParser(description="shiftdeck 安裝工具")
    ap.add_argument("--check", action="store_true", help="只檢查狀態")
    ap.add_argument("--overlay", action="store_true", help="只重新套用覆蓋層")
    args = ap.parse_args()

    lock = load_lock()
    if args.check:
        check(lock)
        return
    if args.overlay:
        apply_overlay(lock)
        return

    fetch_engine(lock)
    apply_overlay(lock)
    install_deps(lock)
    print("\n下一步：把材料放進 projects/，在 AI 工具裡打開本資料夾開始使用。")


if __name__ == "__main__":
    main()
