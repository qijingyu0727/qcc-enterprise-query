#!/usr/bin/env python3
"""Route QCC public API queries and render a detailed report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from basic_details import (
    DETAIL_FIELD_GROUPS as VERIFY_DETAIL_FIELD_GROUPS,
    FULL_DETAIL_FIELDS as VERIFY_FULL_DETAIL_FIELDS,
    MINIMAL_IDENTITY_FIELDS,
    query_basic_details,
)
from fuzzy_search import query_fuzzy_search
from qcc_client import EMPTY_RESULT_HINTS, QccApiError, QccOpenApiClient, compact_text, get_credential_status
from registration_details import (
    DETAIL_FIELD_GROUPS as REGISTRATION_DETAIL_FIELD_GROUPS,
    FULL_DETAIL_FIELDS as REGISTRATION_FULL_DETAIL_FIELDS,
    query_registration_details,
)

CAPABILITY_KEYWORDS = (
    "能干嘛",
    "能做什么",
    "做什么",
    "支持什么",
    "支持哪些",
    "有什么能力",
    "skill 能力",
    "skill功能",
    "skill 功能",
)
DETAIL_KEYWORDS = (
    "工商",
    "企业信息",
    "企业详情",
    "主体信息",
    "法人",
    "法定代表人",
    "注册资本",
    "经营范围",
    "统一社会信用代码",
    "营业期限",
    "上市状态",
    "注册地址",
    "基本信息",
    "核验",
    "人员规模",
    "参保人数",
    "国标行业",
    "更多邮箱",
    "联系信息",
    "企业性质",
    "企业规模",
    "410",
    "2001",
)
FULL_DETAIL_REQUEST_KEYWORDS = (
    "工商",
    "企业信息",
    "企业详情",
    "主体信息",
    "基本信息",
    "核验",
    "核验信息",
    "详情",
)
DETAIL_FIELD_KEYWORD_MAP = {
    "统一社会信用代码": ("统一社会信用代码", "社会信用代码", "信用代码"),
    "法定代表人": ("法定代表人", "法人"),
    "登记状态": ("登记状态", "企业状态"),
    "成立日期": ("成立日期", "成立时间"),
    "注册资本": ("注册资本",),
    "实缴资本": ("实缴资本",),
    "企业类型": ("企业类型",),
    "企业性质": ("企业性质",),
    "注册号": ("注册号",),
    "组织机构代码": ("组织机构代码",),
    "税号": ("税号",),
    "纳税人类型": ("纳税人类型",),
    "企业英文名称": ("企业英文名称", "英文名称"),
    "人员规模": ("人员规模", "企业规模"),
    "参保人数": ("参保人数", "社保人数"),
    "国标行业": ("国标行业", "所属行业", "行业"),
    "企查查行业": ("企查查行业",),
    "所属地区": ("所属地区",),
    "注册地址": ("注册地址", "注册地", "地址"),
    "地址邮编": ("地址邮编", "邮编"),
    "通信地址": ("通信地址", "通讯地址"),
    "通信地址邮编": ("通信地址邮编", "通讯地址邮编"),
    "经营范围": ("经营范围",),
    "营业期限": ("营业期限",),
    "营业期限自": ("营业期限",),
    "营业期限至": ("营业期限",),
    "登记机关": ("登记机关",),
    "核准日期": ("核准日期",),
    "上市状态": ("上市状态", "上市信息", "股票代码"),
    "联系信息": ("联系信息", "联系方式"),
    "电话": ("电话", "联系电话"),
    "更多电话": ("更多电话", "其他电话"),
    "邮箱": ("邮箱",),
    "更多邮箱": ("更多邮箱", "全部邮箱", "更多邮件"),
    "网址": ("网址", "官网"),
    "曾用名": ("曾用名", "历史名称"),
}
REQUEST_FIELD_EXPANSIONS = {
    "联系信息": ["电话", "更多电话", "邮箱", "更多邮箱", "网址"],
    "电话": ["电话", "更多电话"],
    "邮箱": ["邮箱", "更多邮箱"],
    "注册地址": ["所属地区", "注册地址"],
    "营业期限": ["营业期限"],
    "营业期限自": ["营业期限"],
    "营业期限至": ["营业期限"],
}
CLUE_REQUEST_KEYWORDS = (
    "通过电话",
    "根据电话",
    "按电话",
    "通过地址",
    "根据地址",
    "按地址",
    "通过人名",
    "根据人名",
    "按人名",
    "通过产品名",
    "根据产品名",
    "按产品名",
    "通过经营范围",
    "根据经营范围",
    "按经营范围",
    "线索",
    "关键词",
)
UPGRADE_REQUEST_KEYWORDS = (
    "需要",
    "要",
    "需要更多信息",
    "更多信息",
    "更多字段",
    "更详细",
    "更完整",
    "补充信息",
    "补更多",
    "查更多",
)
ADDRESS_HINTS = ("路", "街", "道", "号", "室", "栋", "层", "园区", "大厦")
COMPANY_SUFFIXES = ("公司", "集团", "事务所", "学校", "医院", "研究院", "协会", "合作社", "银行", "中心", "厂")
DETAIL_API_CHOICES = ("410", "2001")
EXPENSIVE_CONFIRM_KEYWORDS = ("确认查询", "确认", "继续查询", "继续", "确认继续", "继续查", "确认查")
DETAIL_API_TITLES = {
    "410": "企业工商信息",
    "2001": "企业信息核验",
}
DETAIL_API_SCRIPT_NAMES = {
    "410": "registration_details.py",
    "2001": "basic_details.py",
}
DETAIL_SELECTION_BASE_FIELDS = (
    "企业名称",
    "统一社会信用代码",
    "法定代表人",
    "登记状态",
    "成立日期",
    "注册资本",
    "企业类型",
    "注册地址",
    "经营范围",
    "营业期限",
    "登记机关",
    "核准日期",
    "上市状态",
)
DETAIL_SELECTION_ENHANCED_FIELDS = (
    "企业性质",
    "人员规模",
    "参保人数",
    "国标行业",
    "企查查行业",
    "电话/更多电话",
    "邮箱/更多邮箱",
    "网址",
    "曾用名",
)
DEFAULT_OVERVIEW_FIELDS = {
    "410": ("统一社会信用代码", "法定代表人", "登记状态", "注册资本", "经营范围"),
    "2001": ("统一社会信用代码", "法定代表人", "登记状态", "企业性质", "人员规模", "参保人数", "国标行业"),
}
DETAIL_API_CONFIG = {
    "410": {
        "title": "企业工商信息",
        "script": "registration_details.py",
        "field_groups": REGISTRATION_DETAIL_FIELD_GROUPS,
        "supported_fields": set(REGISTRATION_FULL_DETAIL_FIELDS),
    },
    "2001": {
        "title": "企业信息核验",
        "script": "basic_details.py",
        "field_groups": VERIFY_DETAIL_FIELD_GROUPS,
        "supported_fields": set(VERIFY_FULL_DETAIL_FIELDS),
    },
}
ENHANCED_ONLY_FIELDS = DETAIL_API_CONFIG["2001"]["supported_fields"] - DETAIL_API_CONFIG["410"]["supported_fields"]


def is_capability_request(user_request: str) -> bool:
    request_text = compact_text(user_request)
    return any(keyword in request_text for keyword in CAPABILITY_KEYWORDS)


def wants_detail_lookup(user_request: str) -> bool:
    request_text = compact_text(user_request)
    if not request_text:
        return True
    return any(keyword in request_text for keyword in DETAIL_KEYWORDS)


def looks_like_credit_code(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9A-Z]{18}", compact_text(value).upper()))


def looks_like_company_name(value: str) -> bool:
    text = compact_text(value)
    if not text:
        return False
    if looks_like_credit_code(text):
        return True
    return any(suffix in text for suffix in COMPANY_SUFFIXES) or "有限" in text


def should_use_fuzzy_directly(company_name: str, user_request: str) -> bool:
    request_text = compact_text(user_request)
    if looks_like_credit_code(company_name):
        return False
    if any(keyword in request_text for keyword in CLUE_REQUEST_KEYWORDS):
        return True
    if re.search(r"\d{7,}", company_name):
        return True
    if any(hint in company_name for hint in ADDRESS_HINTS):
        return True
    return not looks_like_company_name(company_name)


def should_fallback_after_detail_error(exc: QccApiError) -> bool:
    message = compact_text(str(exc))
    return any(hint in message for hint in EMPTY_RESULT_HINTS)


def dedupe_candidates(candidate_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for dataset in candidate_sets:
        for item in dataset.get("results", []):
            key = (compact_text(item.get("企业名称")), compact_text(item.get("统一社会信用代码")))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged[:5]


def dedupe_fields(fields: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for field in fields:
        if field in seen:
            continue
        seen.add(field)
        result.append(field)
    return result


def extract_requested_detail_fields(user_request: str) -> list[str]:
    request_text = compact_text(user_request)
    matched: list[str] = []
    for field, keywords in DETAIL_FIELD_KEYWORD_MAP.items():
        if any(keyword in request_text for keyword in keywords):
            matched.append(field)

    expanded: list[str] = []
    for field in matched:
        expanded.extend(REQUEST_FIELD_EXPANSIONS.get(field, [field]))

    if "邮箱" in request_text and "更多邮箱" in request_text:
        expanded.append("更多邮箱")

    return dedupe_fields(expanded)


def infer_requested_detail_api(user_request: str, detail_api: str | None = None) -> str | None:
    if detail_api:
        normalized = compact_text(detail_api)
        if normalized in DETAIL_API_CHOICES:
            return normalized
        raise QccApiError(f"不支持的详情接口类型：{detail_api}")

    request_text = compact_text(user_request)
    if request_text in ("1", "选1", "第一种", "第1种"):
        return "410"
    if request_text in ("2", "选2", "第二种", "第2种"):
        return "2001"
    if "2001" in request_text or "企业信息核验" in request_text or "核验接口" in request_text:
        return "2001"
    if "410" in request_text or "企业工商信息" in request_text or "工商接口" in request_text:
        return "410"
    return None


def recommend_detail_api(user_request: str) -> tuple[str, str]:
    requested_fields = extract_requested_detail_fields(user_request)
    request_text = compact_text(user_request)
    if any(field in ENHANCED_ONLY_FIELDS for field in requested_fields):
        return "2001", "你这次诉求涉及人员规模、参保人数、联系方式、更多邮箱或行业增强字段，更适合第 2 种查询。"
    if any(keyword in request_text for keyword in ("人员规模", "参保人数", "联系信息", "联系方式", "更多邮箱", "国标行业", "企业性质")):
        return "2001", "你这次诉求更偏增强核验字段，建议直接使用第 2 种查询。"
    return "410", "这次更像基础主体/工商信息查询，优先推荐成本更省的第 1 种查询。"


def requests_enhanced_verification(user_request: str) -> bool:
    requested_fields = extract_requested_detail_fields(user_request)
    request_text = compact_text(user_request)
    if any(field in ENHANCED_ONLY_FIELDS for field in requested_fields):
        return True
    return any(keyword in request_text for keyword in ("人员规模", "参保人数", "联系信息", "联系方式", "更多邮箱", "国标行业", "企业性质"))


def is_upgrade_follow_up_request(user_request: str) -> bool:
    request_text = compact_text(user_request)
    if request_text in UPGRADE_REQUEST_KEYWORDS:
        return True
    return any(keyword in request_text for keyword in ("更多信息", "更详细", "更完整", "补充", "升级"))


def should_default_basic_query(user_request: str) -> bool:
    request_text = compact_text(user_request)
    if not request_text:
        return False
    if is_upgrade_follow_up_request(request_text):
        return False
    if requests_enhanced_verification(request_text):
        return False
    return wants_detail_lookup(request_text)


def is_expensive_query_confirmed(user_request: str, confirm_expensive: bool = False) -> bool:
    if confirm_expensive:
        return True
    request_text = compact_text(user_request)
    return request_text in EXPENSIVE_CONFIRM_KEYWORDS


def prefers_full_detail_output(user_request: str, requested_fields: list[str]) -> bool:
    request_text = compact_text(user_request)
    if any(keyword in request_text for keyword in FULL_DETAIL_REQUEST_KEYWORDS):
        return True
    return not requested_fields


def build_detail_view(user_request: str, detail: dict[str, Any], detail_api: str) -> dict[str, Any]:
    supported_fields = DETAIL_API_CONFIG[detail_api]["supported_fields"]
    requested_fields = [
        field for field in extract_requested_detail_fields(user_request) if field in supported_fields and compact_text(detail.get(field))
    ]
    if prefers_full_detail_output(user_request, requested_fields):
        return {
            "mode": "full",
            "focus_fields": [field for field in DEFAULT_OVERVIEW_FIELDS[detail_api] if compact_text(detail.get(field))],
            "field_groups": DETAIL_API_CONFIG[detail_api]["field_groups"],
        }

    body_fields = dedupe_fields(MINIMAL_IDENTITY_FIELDS + requested_fields)
    request_only_fields = [field for field in body_fields if field not in MINIMAL_IDENTITY_FIELDS]
    field_groups: list[tuple[str, list[str]]] = [("主体识别", MINIMAL_IDENTITY_FIELDS)]
    if request_only_fields:
        field_groups.append(("请求字段", request_only_fields))

    return {
        "mode": "focused",
        "focus_fields": requested_fields,
        "field_groups": field_groups,
    }


def render_detail_sections(detail: dict[str, Any], field_groups: list[tuple[str, list[str]]]) -> list[str]:
    lines: list[str] = []
    for title, fields in field_groups:
        group_lines: list[str] = []
        for field in fields:
            value = compact_text(detail.get(field))
            if value:
                group_lines.append(f"- {field}：**{value}**")
        if not group_lines:
            continue
        lines.extend([f"## {title}", ""])
        lines.extend(group_lines)
        lines.append("")
    return lines


def route_step(script_name: str, output: dict[str, Any], note: str) -> dict[str, Any]:
    result_count = 1 if output.get("has_result") else len(output.get("results", []))
    return {
        "script": script_name,
        "api": output.get("api_title"),
        "query": output.get("query"),
        "note": note,
        "result_count": result_count,
    }


def detail_api_display_name(detail_api: str) -> str:
    if detail_api == "410":
        return "第1种企业工商信息"
    return "第2种企业信息核验"


def build_empty_detail_result(company_name: str, detail_api: str) -> dict[str, Any]:
    return {
        "api_title": DETAIL_API_TITLES[detail_api],
        "query": {"company_name": company_name},
        "has_result": False,
        "result": {},
    }


def capability_payload() -> dict[str, Any]:
    return {
        "mode": "capability",
        "report_markdown": format_capability_markdown(),
        "capabilities": [
            {
                "序号": "1",
                "接口": "企业工商信息",
                "用途": "精确查询企业基础工商主体信息，字段较基础，成本更省",
            },
            {
                "序号": "2",
                "接口": "企业信息核验",
                "用途": "精确查询增强版主体核验详情，可补充人员规模、参保人数、国标行业、联系方式、更多邮箱等，费用更高",
            },
            {
                "序号": "3",
                "接口": "企业模糊搜索",
                "用途": "按企业简称、电话、地址、人名、产品名、经营范围等关键词定位候选企业",
            },
        ],
    }


def credential_required_payload(company_name: str, user_request: str) -> dict[str, Any]:
    status = get_credential_status()
    payload = {
        "mode": "credential_required",
        "company_name": company_name,
        "request": user_request,
        "credential_status": status,
        "report_markdown": "",
    }
    payload["report_markdown"] = format_credential_required_markdown(payload)
    return payload


def detail_api_selection_payload(company_name: str, user_request: str) -> dict[str, Any]:
    recommended_api, reason = recommend_detail_api(user_request)
    payload = {
        "mode": "detail_api_selection",
        "company_name": company_name,
        "request": user_request,
        "recommended_api": recommended_api,
        "recommended_title": DETAIL_API_TITLES[recommended_api],
        "recommendation_reason": reason,
        "basic_scope_fields": list(DETAIL_SELECTION_BASE_FIELDS),
        "enhanced_extra_fields": list(DETAIL_SELECTION_ENHANCED_FIELDS),
        "report_markdown": "",
    }
    payload["report_markdown"] = format_detail_api_selection_markdown(payload)
    return payload


def expensive_confirmation_payload(company_name: str, user_request: str) -> dict[str, Any]:
    request_text = compact_text(user_request) or "补充更多信息"
    payload = {
        "mode": "expensive_confirmation",
        "company_name": company_name,
        "request": request_text,
        "detail_api": "2001",
        "detail_title": DETAIL_API_TITLES["2001"],
        "report_markdown": "",
    }
    payload["report_markdown"] = format_expensive_confirmation_markdown(payload)
    return payload


def clarification_payload(
    company_name: str,
    user_request: str,
    routes: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    payload = {
        "mode": "clarification",
        "company_name": company_name,
        "request": user_request,
        "routes": routes,
        "candidates": candidates,
        "warnings": warnings,
        "report_markdown": "",
    }
    payload["report_markdown"] = format_clarification_markdown(payload)
    return payload


def query_detail_by_api(detail_api: str, company_name: str, client: QccOpenApiClient | None = None) -> dict[str, Any]:
    if detail_api == "410":
        return query_registration_details(company_name, client=client)
    return query_basic_details(company_name, client=client)


def build_unavailable_field_warning(user_request: str, detail_api: str) -> str:
    requested_fields = extract_requested_detail_fields(user_request)
    unsupported = [field for field in requested_fields if field not in DETAIL_API_CONFIG[detail_api]["supported_fields"]]
    if not unsupported:
        return ""
    suggestion_api = "2001" if detail_api == "410" else ""
    if suggestion_api:
        unsupported_text = "、".join(unsupported)
        return (
            f"当前使用的是 {DETAIL_API_TITLES[detail_api]}，未返回字段：{unsupported_text}。"
            "如需这些增强字段，建议改用第 `2` 种查询。"
        )
    return ""


def execute_query(
    company_name: str | None,
    user_request: str,
    client: QccOpenApiClient | None = None,
    detail_api: str | None = None,
    confirm_expensive: bool = False,
    original_request: str | None = None,
) -> dict[str, Any]:
    request_text = compact_text(user_request)
    effective_request = compact_text(original_request) or request_text
    company = compact_text(company_name)

    if is_capability_request(request_text):
        return capability_payload()
    if not request_text:
        raise QccApiError("缺少查询诉求，请说明想查什么。")
    if not company:
        raise QccApiError("缺少企业全称或搜索关键词，请补充后再查询。")

    explicit_detail_api = infer_requested_detail_api(request_text, detail_api=detail_api)
    is_upgrade_follow_up = is_upgrade_follow_up_request(request_text)
    expensive_confirmed = is_expensive_query_confirmed(request_text, confirm_expensive=confirm_expensive)
    if is_upgrade_follow_up:
        expensive_confirmed = True
    original_explicit_api = infer_requested_detail_api(effective_request)

    if not explicit_detail_api and original_explicit_api:
        explicit_detail_api = original_explicit_api

    if not explicit_detail_api and expensive_confirmed:
        if original_explicit_api == "2001" or requests_enhanced_verification(effective_request) or confirm_expensive:
            explicit_detail_api = "2001"

    if client is None and not get_credential_status().get("has_credentials"):
        return credential_required_payload(company, effective_request)

    api_client = client or QccOpenApiClient.from_env()
    routes: list[dict[str, Any]] = []
    warnings: list[str] = []

    if should_use_fuzzy_directly(company, effective_request):
        fuzzy_result = query_fuzzy_search(company, client=api_client)
        routes.append(route_step("fuzzy_search.py", fuzzy_result, "当前输入更像简称或线索关键词，先走企业模糊搜索确认候选企业。"))
        candidates = dedupe_candidates([fuzzy_result])
        if candidates:
            return clarification_payload(company, effective_request, routes, candidates, warnings)

        report = {
            "mode": "query",
            "company_name": company,
            "request": effective_request,
            "routes": routes,
            "detail": None,
            "detail_api": None,
            "detail_source": None,
            "detail_view": None,
            "candidates": [],
            "warnings": warnings,
        }
        report["report_markdown"] = format_query_report(report)
        return report

    if not explicit_detail_api and is_upgrade_follow_up:
        explicit_detail_api = "2001"

    if not explicit_detail_api:
        if requests_enhanced_verification(effective_request):
            return expensive_confirmation_payload(company, effective_request)
        if should_default_basic_query(effective_request):
            explicit_detail_api = "410"
        else:
            return detail_api_selection_payload(company, effective_request)

    if explicit_detail_api == "2001" and not expensive_confirmed:
        return expensive_confirmation_payload(company, effective_request)

    try:
        detail_result = query_detail_by_api(explicit_detail_api, company, client=api_client)
    except QccApiError as exc:
        if not should_fallback_after_detail_error(exc):
            raise
        detail_result = build_empty_detail_result(company, explicit_detail_api)
        warnings.append(f"{DETAIL_API_TITLES[explicit_detail_api]}未直接命中：{compact_text(str(exc))}，已自动回退到企业模糊搜索。")

    routes.append(
        route_step(
            DETAIL_API_SCRIPT_NAMES[explicit_detail_api],
            detail_result,
            f"已按你的选择调用{detail_api_display_name(explicit_detail_api)}。",
        )
    )

    if detail_result.get("has_result"):
        unsupported_warning = build_unavailable_field_warning(effective_request, explicit_detail_api)
        if unsupported_warning:
            warnings.append(unsupported_warning)

        report = {
            "mode": "query",
            "company_name": company,
            "request": effective_request,
            "routes": routes,
            "detail": detail_result["result"],
            "detail_api": explicit_detail_api,
            "detail_source": detail_result.get("api_title"),
            "detail_view": build_detail_view(effective_request, detail_result["result"], explicit_detail_api),
            "candidates": [],
            "warnings": warnings,
        }
        report["report_markdown"] = format_query_report(report)
        return report

    if not warnings:
        warnings.append(f"{DETAIL_API_TITLES[explicit_detail_api]}未直接命中，已自动回退到企业模糊搜索。")

    fuzzy_result = query_fuzzy_search(company, client=api_client)
    routes.append(route_step("fuzzy_search.py", fuzzy_result, "详情接口未命中，改用企业模糊搜索补充候选企业。"))
    candidates = dedupe_candidates([fuzzy_result])

    if candidates:
        return clarification_payload(company, effective_request, routes, candidates, warnings)

    report = {
        "mode": "query",
        "company_name": company,
        "request": effective_request,
        "routes": routes,
        "detail": None,
        "detail_api": explicit_detail_api,
        "detail_source": None,
        "detail_view": None,
        "candidates": [],
        "warnings": warnings,
    }
    report["report_markdown"] = format_query_report(report)
    return report


def format_capability_markdown() -> str:
    lines = ["# QCC 企业查询能力说明", ""]
    lines.extend(["## 使用前提", ""])
    lines.append("- 首次使用前需要提供 `QCC Key` 和 `QCC SecretKey`。")
    lines.append("- skill 会先将凭证写入 `qcc-enterprise-query/.env`，后续复用且不会自动删除。")
    lines.extend(["", "## 可用能力", ""])
    lines.append("- `1. 企业工商信息`：基础工商信息字段较基础，成本更省，适合常规主体信息查询。")
    lines.append("- `2. 企业信息核验`：可额外补充人员规模、参保人数、国标行业、联系方式、更多邮箱等增强字段，但费用更高。")
    lines.append("- `3. 企业模糊搜索`：可按企业简称、电话、地址、人名、产品名、经营范围等关键词返回候选企业。")
    lines.extend(["", "## 输入如何路由", ""])
    lines.append("- 只给了简称、电话、地址或其他线索：先走企业模糊搜索，确认企业全称后，默认先返回基础工商信息。")
    lines.append("- 已给出企业全称或统一社会信用代码，且只是泛查询：默认直接返回 `1. 企业工商信息`。")
    lines.append("- 如果还想补人员规模、参保人数、行业、联系方式等信息，可以在基础结果后直接回复 `需要`；这类继续查询可能会消耗较高费用。")
    lines.append("- 用户已明确说“查企业信息核验”，或诉求命中增强字段时：直接进入高价查询确认，确认后再执行。")
    return "\n".join(lines).rstrip() + "\n"


def format_credential_required_markdown(payload: dict[str, Any]) -> str:
    status = payload["credential_status"]
    lines = ["# 需要先配置企查查凭证", "", "当前 skill 还没有可用的企查查公开接口凭证，所以这次不会直接调接口。"]
    lines.extend(["", "## 当前状态", ""])
    lines.append(f"- 查询诉求：`{payload['request']}`")
    lines.append(f"- 企业/关键词：`{payload['company_name']}`")
    lines.append(f"- 凭证文件：`{status['env_file']}`")
    lines.append(f"- 是否已检测到可用凭证：{'是' if status.get('has_credentials') else '否'}")
    if status.get("app_key_masked"):
        lines.append(f"- 已识别到的 QCC Key：`{status['app_key_masked']}`")
    if status.get("secret_key_masked"):
        lines.append(f"- 已识别到的 QCC SecretKey：`{status['secret_key_masked']}`")
    lines.extend(["", "## 下一步", ""])
    lines.append("- 请直接回复你的 `QCC Key` 和 `QCC SecretKey`。")
    lines.append("- 收到后，skill 会先写入 `qcc-enterprise-query/.env`，然后继续当前查询。")
    return "\n".join(lines).rstrip() + "\n"


def format_detail_api_selection_markdown(payload: dict[str, Any]) -> str:
    basic_scope = "、".join(payload["basic_scope_fields"])
    enhanced_scope = "、".join(payload["enhanced_extra_fields"])
    lines = ["# 企业已确认，请继续选择查询内容", "", "这一步先只确认查询类型，我不会把企业确认和详情查询选择放在同一轮一起执行。"]
    lines.extend(["", "## 当前确认企业", ""])
    lines.append(f"- 企业：`{payload['company_name']}`")
    lines.append(f"- 诉求：`{payload['request']}`")
    lines.extend(["", "## 1. 企业工商信息", ""])
    lines.append("- 适合先看基础工商主体信息，成本更省。")
    lines.append(f"- 通常包含：{basic_scope}。")
    lines.extend(["", "## 2. 企业信息核验", ""])
    lines.append("- 会覆盖基础主体识别信息，并补充更完整的核验字段。")
    lines.append(f"- 相比工商信息，通常额外多出：{enhanced_scope}。")
    lines.append("- 这类查询费用更高，真正执行前我还会再和你确认一次。")
    lines.extend(["", "## 本次建议", ""])
    lines.append(f"- 推荐方式：`{payload['recommended_title']}`")
    lines.append(f"- 推荐原因：{payload['recommendation_reason']}")
    lines.extend(["", "## 请你确认", ""])
    lines.append("- 回复 `1` 或 `企业工商信息`，表示查询基础工商信息。")
    lines.append("- 回复 `2` 或 `企业信息核验`，表示查询增强核验信息。")
    lines.append("- 如果你选择第 `2` 种，我会先说明费用并请你再确认一次。")
    return "\n".join(lines).rstrip() + "\n"


def format_expensive_confirmation_markdown(payload: dict[str, Any]) -> str:
    lines = ["# 查询前再确认一下", "", "你选的是企业信息核验。"]
    lines.extend(["", "## 当前查询", ""])
    lines.append(f"- 企业：`{payload['company_name']}`")
    lines.append(f"- 诉求：`{payload['request']}`")
    lines.extend(["", "## 费用说明", ""])
    lines.append("- 这个查询费用较高。")
    lines.extend(["", "## 下一步", ""])
    lines.append("- 如果确认继续，请直接回复：`确认`。")
    lines.append("- 如果无需查询参保人数、邮箱电话等信息，可以选择基础工商信息，回复 `企业工商信息` 或 `1` 即可。")
    return "\n".join(lines).rstrip() + "\n"


def format_clarification_markdown(payload: dict[str, Any]) -> str:
    lines = ["# 需要先确认目标企业", "", "当前输入还不能直接当成最终企业全称使用，我先按企业模糊搜索找到了候选企业。"]

    lines.extend(["", "## 候选企业", ""])
    lines.extend(build_candidates_table(payload["candidates"]))

    lines.extend(["", "## 查询说明", ""])
    lines.append(f"- 查询输入：`{payload['company_name']}`")
    lines.append(f"- 查询诉求：`{payload['request']}`")
    for index, route in enumerate(payload["routes"], start=1):
        lines.append(
            f"- 第{index}步：`{route['script']}` -> `{route['api']}`，结果数 {route['result_count']}，说明：{route['note']}"
        )
    for warning in payload["warnings"]:
        lines.append(f"- {warning}")

    lines.extend(["", "## 下一步", ""])
    lines.append("- 你要查哪一家？直接回企业全称或者第几个就行。")
    lines.append("- 如果你的诉求只是“查企业信息”这类泛查询，企业确认后我会默认先返回基础工商信息。")
    lines.append("- 如果你本来就想补人员规模、参保人数、行业、联系方式等信息，后面可以继续升级查询；这类结果可能会消耗较高费用。")
    return "\n".join(lines).rstrip() + "\n"


def build_follow_up_suggestions(report: dict[str, Any]) -> list[str]:
    detail = report.get("detail")
    candidates = report.get("candidates", [])
    detail_api = report.get("detail_api")

    if detail:
        if detail_api == "410":
            return [
                "如果你还想继续补充人员规模、参保人数、行业、联系方式等信息，可以直接回复 `需要`；继续查询可能会消耗较高费用。",
                "如果你要，我也可以下一步继续帮你查其他企业，比如 `小米科技有限责任公司`。",
            ]
        return ["如果你要，我可以下一步继续帮你查其他企业，比如 `小米科技有限责任公司`。"]
    if candidates:
        return ["请直接回复其中一家候选企业的完整名称，或者直接回第几个；选中后我会继续帮你往下查。"]
    return ["建议补充更准确的企业全称，或改用电话、地址、人名、产品名、经营范围等线索后重试。"]


def build_candidates_table(records: list[dict[str, Any]]) -> list[str]:
    headers = ["序号", "企业名称", "法定代表人", "企业状态", "成立日期", "统一社会信用代码"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join([" --- "] * len(headers)) + "|"]
    for index, item in enumerate(records[:5], start=1):
        row = [str(index)]
        for header in headers[1:]:
            value = compact_text(item.get(header)) or "-"
            row.append(value.replace("|", "\\|"))
        lines.append("| " + " | ".join(row) + " |")
    return lines


def format_query_report(report: dict[str, Any]) -> str:
    lines = ["# 企查查企业查询报告", ""]
    detail = report.get("detail")
    if detail:
        lines.extend(["查到了，结论如下。", ""])
        field_groups = report.get("detail_view", {}).get("field_groups", [])
        lines.extend(render_detail_sections(detail, field_groups))
    else:
        lines.extend(["本次未查到可识别的主体详情。", ""])

    if report.get("candidates"):
        lines.extend(["## 候选企业", ""])
        lines.extend(build_candidates_table(report["candidates"]))
        lines.append("")

    lines.extend(["## 查询说明", ""])
    lines.append(f"- 查询输入：`{report['company_name']}`")
    lines.append(f"- 查询诉求：`{report['request']}`")
    lines.append(f"- 是否命中主体详情：{'是' if detail else '否'}")
    if report.get("detail_api"):
        lines.append(f"- 本次查询类型：{DETAIL_API_TITLES[report['detail_api']]}")
    for warning in report["warnings"]:
        lines.append(f"- {warning}")
    for index, route in enumerate(report["routes"], start=1):
        lines.append(
            f"- 第{index}步：`{route['script']}` -> `{route['api']}`，结果数 {route['result_count']}，说明：{route['note']}"
        )
    if not report["warnings"]:
        lines.append("- 本次查询按既定路由自动选择接口，未发现额外异常。")

    lines.extend(["", "## 后续建议", ""])
    for suggestion in build_follow_up_suggestions(report):
        lines.append(f"- {suggestion}")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route QCC public API queries and render a report.")
    parser.add_argument("--company-name", help="企业全称或搜索关键词")
    parser.add_argument("--request", required=True, help="自然语言查询诉求")
    parser.add_argument("--detail-api", choices=DETAIL_API_CHOICES, help="显式指定详情接口：410 或 2001")
    parser.add_argument("--confirm-expensive", action="store_true", help="确认继续执行费用更高的 2001 查询")
    parser.add_argument("--original-request", help="保留用户最初查询诉求，供后续确认步骤继续使用")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = execute_query(
            args.company_name,
            args.request,
            detail_api=args.detail_api,
            confirm_expensive=args.confirm_expensive,
            original_request=args.original_request,
        )
    except QccApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["report_markdown"], end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
