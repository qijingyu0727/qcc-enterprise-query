#!/usr/bin/env python3
"""Shared client utilities for the qcc-enterprise-query skill."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

ENV_APP_KEY = "QCC_KEY"
ENV_SECRET_KEY = "QCC_SECRET_KEY"
ENV_FILE_PATH = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_TIMEOUT = 20
DEFAULT_USER_AGENT = "qcc-enterprise-query/1.0"
MISSING_CREDENTIAL_MESSAGE = (
    "未检测到企查查公开接口凭证，请先提供 QCC Key 和 QCC SecretKey，skill 会将其写入 "
    "qcc-enterprise-query/.env 供后续复用。"
)
ENV_ASSIGNMENT_PATTERN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


class QccApiError(RuntimeError):
    """Raised when the QCC OpenAPI returns an error or malformed payload."""


@dataclass(frozen=True)
class ApiSpec:
    name: str
    title: str
    endpoint: str
    query_param: str
    description: str


BASIC_DETAILS_API = ApiSpec(
    name="basic_details",
    title="企业信息核验",
    endpoint="https://api.qichacha.com/EnterpriseInfo/Verify",
    query_param="searchKey",
    description="精确查询企业核验详情。",
)

REGISTRATION_DETAILS_API = ApiSpec(
    name="registration_details",
    title="企业工商信息",
    endpoint="https://api.qichacha.com/ECIV4/GetBasicDetailsByName",
    query_param="keyword",
    description="精确查询企业基础工商主体信息。",
)

FUZZY_SEARCH_API = ApiSpec(
    name="fuzzy_search",
    title="企业模糊搜索",
    endpoint="https://api.qichacha.com/FuzzySearch/GetList",
    query_param="searchKey",
    description="按企业名、人名、产品名、地址、电话、经营范围等关键词搜索企业。",
)

SUCCESS_CODES = {"0", "200", "20000", "success", "ok"}
EMPTY_RESULT_HINTS = ("未查询到", "无匹配", "暂无", "未找到", "无结果", "无数据")


def current_timespan() -> str:
    """Return the QCC timespan header value: Unix timestamp in seconds."""

    return str(int(time.time()))


def compute_token(app_key: str, secret_key: str, timespan: str) -> str:
    raw = f"{app_key}{timespan}{secret_key}".encode("utf-8")
    return hashlib.md5(raw).hexdigest().upper()


def compact_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return " ".join(str(value).replace("\n", " ").split())


def normalize_date(value: Any) -> str:
    text = compact_text(value)
    if text.endswith(" 00:00:00"):
        return text[:-9]
    return text


def first_value(mapping: dict[str, Any], aliases: list[str]) -> Any:
    for key in aliases:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def is_empty_value(value: Any) -> bool:
    if value in (None, "", [], {}):
        return True
    if isinstance(value, dict):
        return all(is_empty_value(item) for item in value.values())
    if isinstance(value, list):
        return len(value) == 0
    return False


def ensure_json_payload(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise QccApiError(f"QCC 返回了非 JSON 响应：{text[:200]}") from exc


def normalize_status_code(value: Any) -> str:
    if value is None:
        return ""
    return compact_text(value).lower()


def unwrap_result(payload: Any) -> Any:
    if isinstance(payload, dict):
        for key in ("Result", "result", "Data", "data"):
            if key in payload:
                return payload[key]
    return payload


def extract_paging(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        paging = payload.get("Paging") or payload.get("paging")
        if isinstance(paging, dict):
            return paging
    return {}


def extract_records(payload: Any) -> list[dict[str, Any]]:
    candidate = unwrap_result(payload)
    if isinstance(candidate, list):
        return [item for item in candidate if isinstance(item, dict)]
    if isinstance(candidate, dict):
        for value in candidate.values():
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return value
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return value
    return []


def infer_match_reason(record: dict[str, Any]) -> str:
    return compact_text(
        first_value(
            record,
            [
                "MatchReason",
                "Reason",
                "ReasonDesc",
                "MatchDesc",
                "匹配原因",
                "HitReason",
            ],
        )
    )


def normalize_candidate_record(record: dict[str, Any], source: str) -> dict[str, Any]:
    normalized = {
        "企业名称": compact_text(first_value(record, ["Name", "企业名称", "CompanyName"])),
        "统一社会信用代码": compact_text(first_value(record, ["CreditCode", "统一社会信用代码"])),
        "法定代表人": compact_text(first_value(record, ["OperName", "法定代表人", "OperPersonName"])),
        "企业状态": compact_text(first_value(record, ["Status", "企业状态", "登记状态"])),
        "成立日期": normalize_date(first_value(record, ["StartDate", "成立日期"])),
        "注册号": compact_text(first_value(record, ["No", "注册号"])),
        "注册地址": compact_text(first_value(record, ["Address", "注册地址"])),
        "匹配原因": infer_match_reason(record),
        "来源": source,
    }
    return {key: value for key, value in normalized.items() if value not in ("", None)}


def summarize_candidate(candidate: dict[str, Any]) -> str:
    fields = [
        candidate.get("企业名称"),
        candidate.get("统一社会信用代码"),
        candidate.get("法定代表人"),
        candidate.get("企业状态"),
    ]
    return " | ".join(item for item in fields if item)


def parse_env_assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = ENV_ASSIGNMENT_PATTERN.match(line)
    if not match:
        return None
    key, value = match.groups()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return key, value


def load_env_file(env_path: Path | None = None) -> dict[str, str]:
    path = env_path or ENV_FILE_PATH
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_assignment(line)
        if parsed:
            key, value = parsed
            values[key] = value
    return values


def mask_secret(value: str) -> str:
    text = compact_text(value)
    if not text:
        return ""
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}***{text[-4:]}"


def _resolve_credential_candidates(
    app_key: str | None = None,
    secret_key: str | None = None,
    env_path: Path | None = None,
) -> dict[str, Any]:
    file_values = load_env_file(env_path=env_path)
    process_key = compact_text(os.getenv(ENV_APP_KEY))
    process_secret = compact_text(os.getenv(ENV_SECRET_KEY))
    explicit_key = compact_text(app_key)
    explicit_secret = compact_text(secret_key)
    env_file = str((env_path or ENV_FILE_PATH).resolve())

    final_key = explicit_key or process_key or compact_text(file_values.get(ENV_APP_KEY))
    final_secret = explicit_secret or process_secret or compact_text(file_values.get(ENV_SECRET_KEY))
    sources = {
        ENV_APP_KEY: "explicit" if explicit_key else "process_env" if process_key else "env_file" if file_values.get(ENV_APP_KEY) else "",
        ENV_SECRET_KEY: (
            "explicit" if explicit_secret else "process_env" if process_secret else "env_file" if file_values.get(ENV_SECRET_KEY) else ""
        ),
    }

    source_summary = ""
    used_sources = {source for source in sources.values() if source}
    if len(used_sources) == 1:
        source_summary = next(iter(used_sources))
    elif used_sources:
        source_summary = "mixed"

    return {
        "has_credentials": bool(final_key and final_secret),
        "app_key": final_key,
        "secret_key": final_secret,
        "app_key_masked": mask_secret(final_key),
        "secret_key_masked": mask_secret(final_secret),
        "sources": sources,
        "source_summary": source_summary,
        "env_file": env_file,
    }


def get_credential_status(
    app_key: str | None = None,
    secret_key: str | None = None,
    env_path: Path | None = None,
) -> dict[str, Any]:
    discovered = _resolve_credential_candidates(app_key=app_key, secret_key=secret_key, env_path=env_path)
    return {
        "has_credentials": discovered["has_credentials"],
        "app_key_masked": discovered["app_key_masked"],
        "secret_key_masked": discovered["secret_key_masked"],
        "sources": discovered["sources"],
        "source_summary": discovered["source_summary"],
        "env_file": discovered["env_file"],
    }


def write_credentials_to_env(
    app_key: str,
    secret_key: str,
    env_path: Path | None = None,
) -> dict[str, Any]:
    final_key = compact_text(app_key)
    final_secret = compact_text(secret_key)
    if not final_key or not final_secret:
        raise QccApiError("写入企查查凭证时失败：QCC Key 和 QCC SecretKey 都不能为空。")

    path = env_path or ENV_FILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    updated_lines: list[str] = []
    written_keys: set[str] = set()
    replacements = {
        ENV_APP_KEY: final_key,
        ENV_SECRET_KEY: final_secret,
    }

    for line in existing_lines:
        parsed = parse_env_assignment(line)
        if not parsed:
            updated_lines.append(line)
            continue
        key, _ = parsed
        if key in replacements:
            updated_lines.append(f"{key}={replacements[key]}")
            written_keys.add(key)
            continue
        updated_lines.append(line)

    if updated_lines and updated_lines[-1].strip():
        updated_lines.append("")
    for key in (ENV_APP_KEY, ENV_SECRET_KEY):
        if key not in written_keys:
            updated_lines.append(f"{key}={replacements[key]}")

    content = "\n".join(updated_lines).rstrip() + "\n"
    path.write_text(content, encoding="utf-8")
    return get_credential_status(env_path=path)


def resolve_credentials(
    app_key: str | None = None,
    secret_key: str | None = None,
    env_path: Path | None = None,
) -> tuple[str, str]:
    discovered = _resolve_credential_candidates(app_key=app_key, secret_key=secret_key, env_path=env_path)
    if discovered["has_credentials"]:
        return discovered["app_key"], discovered["secret_key"]
    raise QccApiError(MISSING_CREDENTIAL_MESSAGE)


class QccOpenApiClient:
    """Minimal QCC OpenAPI client for the enabled public interfaces."""

    def __init__(self, app_key: str, secret_key: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.app_key = app_key
        self.secret_key = secret_key
        self.timeout = timeout

    @classmethod
    def from_env(cls, timeout: int = DEFAULT_TIMEOUT) -> "QccOpenApiClient":
        return cls(*resolve_credentials(), timeout=timeout)

    def build_headers(self, timespan: str | None = None) -> dict[str, str]:
        ts = timespan or current_timespan()
        return {
            "Token": compute_token(self.app_key, self.secret_key, ts),
            "Timespan": ts,
            "User-Agent": DEFAULT_USER_AGENT,
        }

    def get(self, api: ApiSpec, query_value: str, extra_params: dict[str, Any] | None = None) -> Any:
        params: dict[str, Any] = {"key": self.app_key, api.query_param: query_value}
        if extra_params:
            for key, value in extra_params.items():
                if value not in (None, "", [], {}):
                    params[key] = value
        url = f"{api.endpoint}?{parse.urlencode(params)}"
        request_obj = request.Request(url, headers=self.build_headers(), method="GET")

        try:
            with request.urlopen(request_obj, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise QccApiError(f"{api.title} 请求失败：HTTP {exc.code}，{detail or exc.reason}") from exc
        except error.URLError as exc:
            raise QccApiError(f"{api.title} 请求失败：{exc.reason}") from exc

        payload = ensure_json_payload(body)
        self._ensure_success(payload, api.title)
        return payload

    def _ensure_success(self, payload: Any, api_title: str) -> None:
        if not isinstance(payload, dict):
            return

        status = normalize_status_code(
            first_value(payload, ["Status", "status", "Code", "code", "ResultCode", "resultCode"])
        )
        message = compact_text(first_value(payload, ["Message", "message", "ErrorMessage", "errorMessage"]))

        if status and status not in SUCCESS_CODES:
            if any(hint in message for hint in EMPTY_RESULT_HINTS):
                return
            raise QccApiError(f"{api_title} 返回异常：{status} {message}".strip())
