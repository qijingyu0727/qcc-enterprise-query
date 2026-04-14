#!/usr/bin/env python3
"""Query QCC public API: fuzzy enterprise search."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from qcc_client import FUZZY_SEARCH_API, QccApiError, QccOpenApiClient, extract_paging, extract_records, normalize_candidate_record


def query_fuzzy_search(search_key: str, page_index: int = 1, client: QccOpenApiClient | None = None) -> dict[str, object]:
    api_client = client or QccOpenApiClient.from_env()
    extra_params = {"pageIndex": page_index} if page_index and page_index > 1 else None
    raw = api_client.get(FUZZY_SEARCH_API, search_key, extra_params=extra_params)
    records = [normalize_candidate_record(item, "企业模糊搜索") for item in extract_records(raw)]
    return {
        "api": FUZZY_SEARCH_API.name,
        "api_title": FUZZY_SEARCH_API.title,
        "endpoint": FUZZY_SEARCH_API.endpoint,
        "query": {"search_key": search_key, "page_index": page_index},
        "results": records,
        "paging": extract_paging(raw),
        "raw": raw,
    }


def build_table(records: list[dict[str, object]]) -> list[str]:
    headers = ["序号", "企业名称", "法定代表人", "企业状态", "成立日期", "统一社会信用代码"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join([" --- "] * len(headers)) + "|"]
    for index, item in enumerate(records[:5], start=1):
        row = [str(index)]
        row.extend(str(item.get(header, "-") or "-").replace("|", "\\|") for header in headers[1:])
        lines.append("| " + " | ".join(row) + " |")
    return lines


def format_markdown_report(output: dict[str, object]) -> str:
    results = output["results"]
    lines = ["# 企业模糊搜索结果", "", "## 查询摘要", ""]
    lines.append(f"- 搜索关键词：{output['query']['search_key']}")
    lines.append(f"- 接口：{output['api_title']}")
    lines.append(f"- 返回候选数：{len(results)}")
    lines.extend(["", "## 候选企业", ""])
    if not results:
        lines.append("- 本次接口未返回可识别结果。")
        lines.append("- 建议更换关键词，或提供更接近企业全称的线索重试。")
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(build_table(results))
    lines.extend(["", "## 下一步", ""])
    lines.append("- 你要查哪一家？直接回企业全称或者第几个就行。")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query QCC fuzzy enterprise search.")
    parser.add_argument("--search-key", required=True, help="电话、地址、人名、产品名、经营范围等关键词")
    parser.add_argument("--page-index", type=int, default=1, help="页码，默认 1")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = query_fuzzy_search(args.search_key, page_index=args.page_index)
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
