#!/usr/bin/env python3
"""Inject or restore the score-reset demo fault without discarding other edits."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inject", "restore"))
    parser.add_argument("--app", type=Path, default=Path("app/index.html"))
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    state = args.state_dir.resolve()
    metadata = state / "fault.json"
    backup = state / "index.html.original"
    current = app.read_bytes()

    if args.action == "inject":
        if metadata.exists() or backup.exists():
            parser.error("此目录已有备份；请先恢复，或为新的演示使用新的状态目录。")
        source = b"            STATE.score = 0;"
        replacement = b"            // DEMO FAULT: keep the previous score."
        if current.count(source) != 1:
            parser.error("得分清零代码不再唯一匹配；未修改应用，请核对当前实现。")
        modified = current.replace(source, replacement, 1)
        state.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(current)
        metadata.write_text(
            json.dumps(
                {
                    "app": str(app),
                    "original_sha256": digest(current),
                    "injected_sha256": digest(modified),
                },
                indent=2,
            ) + "\n"
        )
        app.write_bytes(modified)
        print("已注入：新一轮挑战保留旧得分。原文件已备份。")
    else:
        if not metadata.exists() or not backup.exists():
            parser.error("缺少本次注入的备份或记录；未修改应用。")
        record = json.loads(metadata.read_text())
        original = backup.read_bytes()
        if record["app"] != str(app) or digest(original) != record["original_sha256"]:
            parser.error("应用路径或备份校验不一致；未修改应用。")
        if digest(current) != record["injected_sha256"]:
            parser.error("注入后应用又发生了修改；拒绝覆盖，请人工核对差异。")
        app.write_bytes(original)
        metadata.unlink()
        backup.unlink()
        print("已按字节恢复本次注入前的应用文件。")


if __name__ == "__main__":
    main()
