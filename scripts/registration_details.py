#!/usr/bin/env python3
"""Query QCC public API: enterprise registration details (410)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from qcc_client import (
    QccApiError,
    QccOpenApiClient,
    REGISTRATION_DETAILS_API,
    compact_text,
    first_value,
    normalize_date,
    unwrap_result,
)

CORE_SUMMARY_FIELDS = [
    "企业名称",
    "统一社会信用代码",
    "法定代表人",
    "登记状态",
    "成立日期",
    "注册资本",
    "企业类型",
]

BUSINESS_AND_ADDRESS_FIELDS = [
    "所属地区",
    "注册地址",
    "经营范围",
]

OTHER_VERIFY_FIELDS = [
    "营业期限",
    "登记机关",
    "核准日期",
    "上市状态",
]

DETAIL_FIELD_GROUPS = [
    ("核心结论", CORE_SUMMARY_FIELDS),
    ("经营与地址", BUSINESS_AND_ADDRESS_FIELDS),
    ("其他信息", OTHER_VERIFY_FIELDS),
]

MINIMAL_IDENTITY_FIELDS = ["企业名称", "统一社会信用代码", "法定代表人", "登记状态"]
FULL_DETAIL_FIELDS = [field for _, fields in DETAIL_FIELD_GROUPS for field in fields]


def compact_term(start: Any, end: Any) -> str:
    start_text = normalize_date(start)
    end_text = normalize_date(end)
    if start_text and end_text:
        return f"{start_text} 至 {end_text}"
    if start_text:
        return f"{start_text} 起"
    if end_text:
        return f"至 {end_text}"
    return ""


def normalize_listing_status(raw: dict[str, Any]) -> str:
    stock_flag = compact_text(first_value(raw, ["IsOnStock", "上市状态"]))
    stock_number = compact_text(first_value(raw, ["StockNumber", "股票代码"]))
    stock_type = compact_text(first_value(raw, ["StockType", "上市类型"]))

    if stock_flag in ("1", "true", "True", "是"):
        listing = "已上市"
    elif stock_flag in ("0", "false", "False", "否"):
        listing = "未上市"
    else:
        listing = stock_flag

    details = [item for item in [listing, stock_type, stock_number] if item]
    return " / ".join(details)


def normalize_registration_details(payload: Any) -> dict[str, Any]:
    raw = unwrap_result(payload)
    if isinstance(raw, dict) and isinstance(raw.get("Data"), dict):
        raw = raw["Data"]
    if not isinstance(raw, dict):
        return {}

    area = raw.get("Area") if isinstance(raw.get("Area"), dict) else {}
    area_parts = [compact_text(area.get(key)) for key in ("Province", "City", "County")]

    normalized = {
        "企业名称": compact_text(first_value(raw, ["Name", "企业名称"])),
        "统一社会信用代码": compact_text(first_value(raw, ["CreditCode", "统一社会信用代码"])),
        "法定代表人": compact_text(first_value(raw, ["OperName", "法定代表人"])),
        "登记状态": compact_text(first_value(raw, ["Status", "登记状态"])),
        "成立日期": normalize_date(first_value(raw, ["StartDate", "成立日期"])),
        "注册资本": compact_text(first_value(raw, ["RegistCapi", "RegisteredCapital", "注册资本"])),
        "企业类型": compact_text(first_value(raw, ["EconKind", "企业类型"])),
        "所属地区": " / ".join(part for part in area_parts if part),
        "注册地址": compact_text(first_value(raw, ["Address", "注册地址"])),
        "经营范围": compact_text(first_value(raw, ["Scope", "经营范围"])),
        "营业期限": compact_term(first_value(raw, ["TermStart", "营业期限自"]), first_value(raw, ["TermEnd", "营业期限至"])),
        "登记机关": compact_text(first_value(raw, ["BelongOrg", "登记机关"])),
        "核准日期": normalize_date(first_value(raw, ["CheckDate", "核准日期"])),
        "上市状态": normalize_listing_status(raw),
    }
    return {key: value for key, value in normalized.items() if value}


def query_registration_details(company_name: str, client: QccOpenApiClient | None = None) -> dict[str, Any]:
    api_client = client or QccOpenApiClient.from_env()
    raw = api_client.get(REGISTRATION_DETAILS_API, company_name)
    result = normalize_registration_details(raw)
    return {
        "api": REGISTRATION_DETAILS_API.name,
        "api_title": REGISTRATION_DETAILS_API.title,
        "endpoint": REGISTRATION_DETAILS_API.endpoint,
        "query": {"company_name": company_name},
        "has_result": bool(result),
        "result": result,
        "raw": raw,
    }


def format_markdown_report(output: dict[str, Any]) -> str:
    lines = ["# 企业工商信息查询结果", ""]

    if not output["has_result"]:
        lines.extend(["本次未查到可识别结果。", "", "## 查询摘要", ""])
        lines.append(f"- 查询企业：{output['query']['company_name']}")
        lines.append(f"- 接口：{output['api_title']}")
        lines.append("- 本次接口未返回可识别结果。")
        lines.append("- 建议确认企业全称，或改用企业模糊搜索进一步定位目标企业。")
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(["查到了，结论如下。", ""])
    for title, fields in DETAIL_FIELD_GROUPS:
        group_lines: list[str] = []
        for field in fields:
            value = output["result"].get(field)
            if value:
                group_lines.append(f"- {field}：**{value}**")
        if not group_lines:
            continue
        lines.extend([f"## {title}", ""])
        lines.extend(group_lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query QCC enterprise registration details (410).")
    parser.add_argument("--company-name", required=True, help="企业全称或统一社会信用代码")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = query_registration_details(args.company_name)
    except QccApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_markdown_report(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
