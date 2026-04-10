#!/usr/bin/env python3
"""Query QCC public API: enterprise verify details."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from qcc_client import BASIC_DETAILS_API, QccApiError, QccOpenApiClient, compact_text, first_value, normalize_date, unwrap_result


ENTITY_TYPE_LABELS = {
    "-1": "其他",
    "0": "大陆企业",
    "1": "社会组织",
    "4": "事业单位",
    "7": "医院",
    "9": "律师事务所",
    "10": "学校",
    "11": "机关单位",
}

CORE_SUMMARY_FIELDS = [
    "企业名称",
    "统一社会信用代码",
    "法定代表人",
    "登记状态",
    "成立日期",
    "注册资本",
    "实缴资本",
    "企业类型",
    "企业性质",
    "注册号",
    "组织机构代码",
    "税号",
    "纳税人类型",
    "企业英文名称",
]

SCALE_AND_INDUSTRY_FIELDS = [
    "人员规模",
    "参保人数",
    "国标行业",
    "企查查行业",
    "经营范围",
]

CONTACT_FIELDS = [
    "电话",
    "更多电话",
    "邮箱",
    "更多邮箱",
    "网址",
]

ADDRESS_FIELDS = [
    "所属地区",
    "注册地址",
    "地址邮编",
    "通信地址",
    "通信地址邮编",
]

OTHER_VERIFY_FIELDS = [
    "营业期限",
    "登记机关",
    "核准日期",
    "上市状态",
    "曾用名",
]

DETAIL_FIELD_GROUPS = [
    ("核心结论", CORE_SUMMARY_FIELDS),
    ("行业与经营范围", SCALE_AND_INDUSTRY_FIELDS),
    ("联系方式", CONTACT_FIELDS),
    ("地址信息", ADDRESS_FIELDS),
    ("其他信息", OTHER_VERIFY_FIELDS),
]

MINIMAL_IDENTITY_FIELDS = ["企业名称", "统一社会信用代码", "法定代表人", "登记状态"]
FULL_DETAIL_FIELDS = [field for _, fields in DETAIL_FIELD_GROUPS for field in fields]


def unique_texts(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = compact_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def compact_money(text_value: Any, amount: Any, unit: Any, currency: Any) -> str:
    direct = compact_text(text_value)
    if direct:
        return direct

    amount_text = compact_text(amount)
    unit_text = compact_text(unit)
    currency_text = compact_text(currency)
    if not any((amount_text, unit_text, currency_text)):
        return ""
    return compact_text(f"{amount_text}{unit_text}{currency_text}")


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


def join_nested_labels(raw: dict[str, Any], key: str, aliases: list[str]) -> str:
    nested = raw.get(key) if isinstance(raw.get(key), dict) else {}
    parts = [compact_text(nested.get(alias)) for alias in aliases]
    return " / ".join(part for part in parts if part)


def extract_original_names(raw: dict[str, Any]) -> str:
    original_names = raw.get("OriginalName") if isinstance(raw.get("OriginalName"), list) else []
    names = unique_texts([item.get("Name") if isinstance(item, dict) else item for item in original_names])
    return "；".join(names)


def normalize_entity_type(raw: dict[str, Any]) -> str:
    value = compact_text(first_value(raw, ["EntType", "企业性质"]))
    return ENTITY_TYPE_LABELS.get(value, value)


def extract_contact_info(raw: dict[str, Any]) -> dict[str, str]:
    contact = raw.get("ContactInfo") if isinstance(raw.get("ContactInfo"), dict) else {}
    if not contact:
        return {}

    tel = compact_text(first_value(contact, ["Tel", "联系电话", "Phone"]))
    email = compact_text(first_value(contact, ["Email", "邮箱"]))

    website_list = contact.get("WebSiteList") if isinstance(contact.get("WebSiteList"), list) else []
    websites = unique_texts([item.get("Url") if isinstance(item, dict) else item for item in website_list])

    more_email_list = contact.get("MoreEmailList") if isinstance(contact.get("MoreEmailList"), list) else []
    more_emails = unique_texts([item.get("Email") if isinstance(item, dict) else item for item in more_email_list])

    more_tel_list = contact.get("MoreTelList") if isinstance(contact.get("MoreTelList"), list) else []
    more_tels = unique_texts(
        [
            item.get("Tel") if isinstance(item, dict) else item
            for item in more_tel_list
        ]
    )

    parts: list[str] = []
    if tel:
        parts.append(f"电话：{tel}")
    if more_tels:
        parts.append(f"更多电话：{'；'.join(more_tels)}")
    if email:
        parts.append(f"邮箱：{email}")
    if websites:
        parts.append(f"网址：{'；'.join(websites)}")

    result = {
        "电话": tel,
        "更多电话": "；".join(more_tels),
        "邮箱": email,
        "更多邮箱": "；".join(more_emails),
        "网址": "；".join(websites),
        "联系信息": "；".join(parts),
    }
    return {key: value for key, value in result.items() if value}


def normalize_listing_status(raw: dict[str, Any]) -> str:
    stock_info = raw.get("StockInfo") if isinstance(raw.get("StockInfo"), dict) else {}
    stock_flag = compact_text(first_value(raw, ["IsOnStock", "上市状态"]))
    stock_number = compact_text(first_value(stock_info, ["StockNumber", "股票代码"])) or compact_text(
        first_value(raw, ["StockNumber", "股票代码"])
    )
    stock_type = compact_text(first_value(stock_info, ["StockType", "上市类型"])) or compact_text(
        first_value(raw, ["StockType", "上市类型"])
    )

    if stock_number or stock_type:
        listing = "已上市"
    elif stock_flag in ("1", "true", "True", "是"):
        listing = "已上市"
    elif stock_flag in ("0", "false", "False", "否"):
        listing = "未上市"
    else:
        listing = stock_flag

    details = [item for item in [listing, stock_type, stock_number] if item]
    return " / ".join(details)


def normalize_basic_details(payload: Any) -> dict[str, Any]:
    raw = unwrap_result(payload)
    if isinstance(raw, dict) and isinstance(raw.get("Data"), dict):
        raw = raw["Data"]
    if not isinstance(raw, dict):
        return {}

    contact_fields = extract_contact_info(raw)

    person_scope = compact_text(first_value(raw, ["PersonScope", "人员规模"]))

    normalized = {
        "企业名称": compact_text(first_value(raw, ["Name", "企业名称"])),
        "统一社会信用代码": compact_text(first_value(raw, ["CreditCode", "统一社会信用代码"])),
        "法定代表人": compact_text(first_value(raw, ["OperName", "法定代表人"])),
        "登记状态": compact_text(first_value(raw, ["Status", "登记状态"])),
        "成立日期": normalize_date(first_value(raw, ["StartDate", "成立日期"])),
        "注册资本": compact_money(
            first_value(raw, ["RegistCapi", "注册资本"]),
            first_value(raw, ["RegisteredCapital", "注册资本金额"]),
            first_value(raw, ["RegisteredCapitalUnit", "注册资本单位"]),
            first_value(raw, ["RegisteredCapitalCCY", "注册资本币种"]),
        ),
        "实缴资本": compact_money(
            first_value(raw, ["RealCapi", "实缴资本"]),
            first_value(raw, ["PaidUpCapital", "实缴资本金额"]),
            first_value(raw, ["PaidUpCapitalUnit", "实缴资本单位"]),
            first_value(raw, ["PaidUpCapitalCCY", "实缴资本币种"]),
        ),
        "企业类型": compact_text(first_value(raw, ["EconKind", "企业类型"])),
        "企业性质": normalize_entity_type(raw),
        "注册号": compact_text(first_value(raw, ["No", "注册号"])),
        "组织机构代码": compact_text(first_value(raw, ["OrgNo", "组织机构代码"])),
        "税号": compact_text(first_value(raw, ["TaxNo", "税号"])),
        "纳税人类型": compact_text(first_value(raw, ["TaxpayerType", "纳税人类型"])),
        "企业英文名称": compact_text(first_value(raw, ["EnglishName", "企业英文名称"])),
        "人员规模": person_scope,
        "参保人数": compact_text(first_value(raw, ["InsuredCount", "参保人数"])),
        "企业规模": person_scope,
        "国标行业": join_nested_labels(raw, "Industry", ["Industry", "SubIndustry", "MiddleCategory", "SmallCategory"]),
        "企查查行业": join_nested_labels(raw, "QccIndustry", ["AName", "BName", "CName", "DName"]),
        "注册地址": compact_text(first_value(raw, ["Address", "注册地址"])),
        "地址邮编": compact_text(first_value(raw, ["AddressPostalCode", "地址邮编"])),
        "通信地址": compact_text(first_value(raw, ["AnnualAddress", "通信地址"])),
        "通信地址邮编": compact_text(first_value(raw, ["AnnualAddressPostalCode", "通信地址邮编"])),
        "经营范围": compact_text(first_value(raw, ["Scope", "经营范围"])),
        "营业期限": compact_term(first_value(raw, ["TermStart", "营业期限自"]), first_value(raw, ["TermEnd", "营业期限至"])),
        "营业期限自": normalize_date(first_value(raw, ["TermStart", "营业期限自"])),
        "营业期限至": normalize_date(first_value(raw, ["TermEnd", "营业期限至"])),
        "所属地区": join_nested_labels(raw, "Area", ["Province", "City", "County"]),
        "登记机关": compact_text(first_value(raw, ["BelongOrg", "登记机关"])),
        "核准日期": normalize_date(first_value(raw, ["CheckDate", "核准日期"])),
        "上市状态": normalize_listing_status(raw),
        "曾用名": extract_original_names(raw),
    }
    normalized.update(contact_fields)
    return {key: value for key, value in normalized.items() if value}


def query_basic_details(company_name: str, client: QccOpenApiClient | None = None) -> dict[str, Any]:
    api_client = client or QccOpenApiClient.from_env()
    raw = api_client.get(BASIC_DETAILS_API, company_name)
    result = normalize_basic_details(raw)
    return {
        "api": BASIC_DETAILS_API.name,
        "api_title": BASIC_DETAILS_API.title,
        "endpoint": BASIC_DETAILS_API.endpoint,
        "query": {"company_name": company_name},
        "has_result": bool(result),
        "result": result,
        "raw": raw,
    }


def format_markdown_report(output: dict[str, Any]) -> str:
    lines = ["# 企业信息核验结果", ""]

    if not output["has_result"]:
        lines.extend(["本次未查到可识别结果。", "", "## 查询摘要", ""])
        lines.append(f"- 查询企业：{output['query']['company_name']}")
        lines.append(f"- 接口：{output['api_title']}")
        lines.append("- 本次接口未返回可识别结果。")
        lines.append("- 建议改用企业模糊搜索进一步确认候选企业。")
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
    parser = argparse.ArgumentParser(description="Query QCC enterprise verify details.")
    parser.add_argument("--company-name", required=True, help="企业全称或统一社会信用代码")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = query_basic_details(args.company_name)
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
