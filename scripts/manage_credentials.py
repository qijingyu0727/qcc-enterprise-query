#!/usr/bin/env python3
"""Manage local QCC API credentials for the skill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from qcc_client import ENV_FILE_PATH, QccApiError, get_credential_status, write_credentials_to_env


def build_payload(action: str, status: dict[str, object]) -> dict[str, object]:
    return {
        "mode": "credential_status",
        "action": action,
        "has_credentials": bool(status.get("has_credentials")),
        "source_summary": status.get("source_summary"),
        "env_file": status.get("env_file"),
        "app_key_masked": status.get("app_key_masked"),
        "secret_key_masked": status.get("secret_key_masked"),
    }


def format_markdown(payload: dict[str, object]) -> str:
    lines = ["# QCC 凭证状态", ""]
    if payload["has_credentials"]:
        lines.append("已检测到可用的企查查凭证。")
    else:
        lines.append("当前还没有配置可用的企查查凭证。")

    lines.extend(["", "## 当前状态", ""])
    lines.append(f"- 动作：`{payload['action']}`")
    lines.append(f"- 凭证文件：`{payload['env_file']}`")
    lines.append(f"- 是否可用：{'是' if payload['has_credentials'] else '否'}")
    if payload.get("source_summary"):
        lines.append(f"- 来源：`{payload['source_summary']}`")
    if payload.get("app_key_masked"):
        lines.append(f"- QCC Key：`{payload['app_key_masked']}`")
    if payload.get("secret_key_masked"):
        lines.append(f"- QCC SecretKey：`{payload['secret_key_masked']}`")

    if not payload["has_credentials"]:
        lines.extend(["", "## 下一步", ""])
        lines.append("- 请提供 `QCC Key` 和 `QCC SecretKey`，skill 会将其写入本地 `.env` 后继续查询。")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage QCC skill credentials.")
    parser.add_argument("--app-key", help="QCC AppKey / Key")
    parser.add_argument("--secret-key", help="QCC SecretKey")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if bool(args.app_key) ^ bool(args.secret_key):
            raise QccApiError("写入凭证时需要同时提供 --app-key 和 --secret-key。")

        if args.app_key and args.secret_key:
            status = write_credentials_to_env(args.app_key, args.secret_key, env_path=ENV_FILE_PATH)
            payload = build_payload("save", status)
        else:
            payload = build_payload("status", get_credential_status(env_path=ENV_FILE_PATH))
    except QccApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
