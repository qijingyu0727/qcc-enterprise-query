from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_query


class RunQueryTest(unittest.TestCase):
    def test_capability_request_skips_api_calls(self) -> None:
        with mock.patch("run_query.query_basic_details", side_effect=AssertionError("should not call")), mock.patch(
            "run_query.query_registration_details", side_effect=AssertionError("should not call")
        ), mock.patch("run_query.query_fuzzy_search", side_effect=AssertionError("should not call")):
            result = run_query.execute_query(None, "这个 skill 能干嘛")

        self.assertEqual(result["mode"], "capability")
        self.assertIn("410 企业工商信息", result["report_markdown"])
        self.assertIn("2001 企业信息核验", result["report_markdown"])
        self.assertIn("886 企业模糊搜索", result["report_markdown"])

    def test_missing_credentials_returns_credential_required(self) -> None:
        fake_status = {
            "has_credentials": False,
            "env_file": "/tmp/qcc/.env",
            "app_key_masked": "",
            "secret_key_masked": "",
        }
        with mock.patch("run_query.get_credential_status", return_value=fake_status):
            result = run_query.execute_query("杭州飞致云信息科技有限公司", "查企业信息")

        self.assertEqual(result["mode"], "credential_required")
        self.assertIn("需要先配置企查查凭证", result["report_markdown"])

    def test_full_company_name_without_selected_api_returns_selection(self) -> None:
        result = run_query.execute_query("杭州飞致云信息科技有限公司", "查企业基本信息", client=object())

        self.assertEqual(result["mode"], "detail_api_selection")
        self.assertEqual(result["recommended_api"], "410")
        self.assertIn("请确认本次查询方式", result["report_markdown"])

    def test_enhanced_request_requires_expensive_confirmation(self) -> None:
        result = run_query.execute_query("杭州飞致云信息科技有限公司", "查人员规模和参保人数", client=object())

        self.assertEqual(result["mode"], "expensive_confirmation")
        self.assertEqual(result["detail_api"], "2001")
        self.assertIn("费用相对更高", result["report_markdown"])
        self.assertIn("确认查询", result["report_markdown"])

    def test_selection_prompt_accepts_numeric_choices(self) -> None:
        result = run_query.execute_query("杭州飞致云信息科技有限公司", "查企业基本信息", client=object())

        self.assertIn("回复 `1`", result["report_markdown"])
        self.assertIn("回复 `2`", result["report_markdown"])
        self.assertIn("再和你确认一次", result["report_markdown"])

    def test_full_company_name_with_410_calls_registration_details_only(self) -> None:
        registration_result = {
            "api_title": "企业工商信息",
            "query": {"company_name": "企查查科技股份有限公司"},
            "has_result": True,
            "result": {
                "企业名称": "企查查科技股份有限公司",
                "统一社会信用代码": "913200000000000000",
                "法定代表人": "唐某",
            },
        }
        with mock.patch("run_query.query_registration_details", return_value=registration_result) as mock_registration, mock.patch(
            "run_query.query_basic_details", side_effect=AssertionError("should not call")
        ), mock.patch("run_query.query_fuzzy_search", side_effect=AssertionError("should not call")):
            result = run_query.execute_query("企查查科技股份有限公司", "查企业基本信息", client=object(), detail_api="410")

        self.assertTrue(mock_registration.called)
        self.assertEqual(result["detail_api"], "410")
        self.assertEqual([item["script"] for item in result["routes"]], ["registration_details.py"])

    def test_numeric_choice_1_maps_to_410(self) -> None:
        registration_result = {
            "api_title": "企业工商信息",
            "query": {"company_name": "企查查科技股份有限公司"},
            "has_result": True,
            "result": {"企业名称": "企查查科技股份有限公司"},
        }
        with mock.patch("run_query.query_registration_details", return_value=registration_result) as mock_registration:
            result = run_query.execute_query("企查查科技股份有限公司", "1", client=object())

        self.assertTrue(mock_registration.called)
        self.assertEqual(result["detail_api"], "410")

    def test_numeric_choice_1_keeps_original_request_in_report(self) -> None:
        registration_result = {
            "api_title": "企业工商信息",
            "query": {"company_name": "企查查科技股份有限公司"},
            "has_result": True,
            "result": {"企业名称": "企查查科技股份有限公司"},
        }
        with mock.patch("run_query.query_registration_details", return_value=registration_result):
            result = run_query.execute_query(
                "企查查科技股份有限公司",
                "1",
                client=object(),
                original_request="查企业基本信息",
            )

        self.assertEqual(result["detail_api"], "410")
        self.assertEqual(result["request"], "查企业基本信息")
        self.assertIn("查询诉求：`查企业基本信息`", result["report_markdown"])

    def test_full_company_name_with_2001_calls_verify_details_only(self) -> None:
        basic_result = {
            "api_title": "企业信息核验",
            "query": {"company_name": "企查查科技股份有限公司"},
            "has_result": True,
            "result": {
                "企业名称": "企查查科技股份有限公司",
                "统一社会信用代码": "913200000000000000",
                "法定代表人": "唐某",
                "人员规模": "100-499人",
            },
        }
        with mock.patch("run_query.query_basic_details", return_value=basic_result) as mock_basic, mock.patch(
            "run_query.query_registration_details", side_effect=AssertionError("should not call")
        ), mock.patch("run_query.query_fuzzy_search", side_effect=AssertionError("should not call")):
            result = run_query.execute_query(
                "企查查科技股份有限公司",
                "查企业基本信息",
                client=object(),
                detail_api="2001",
                confirm_expensive=True,
            )

        self.assertTrue(mock_basic.called)
        self.assertEqual(result["detail_api"], "2001")
        self.assertEqual([item["script"] for item in result["routes"]], ["basic_details.py"])

    def test_numeric_choice_2_requires_expensive_confirmation(self) -> None:
        result = run_query.execute_query(
            "企查查科技股份有限公司",
            "2",
            client=object(),
            original_request="查企业基本信息",
        )

        self.assertEqual(result["mode"], "expensive_confirmation")
        self.assertEqual(result["detail_api"], "2001")
        self.assertEqual(result["request"], "查企业基本信息")
        self.assertIn("企业信息核验", result["report_markdown"])

    def test_numeric_choice_2_with_confirm_expensive_calls_2001(self) -> None:
        basic_result = {
            "api_title": "企业信息核验",
            "query": {"company_name": "企查查科技股份有限公司"},
            "has_result": True,
            "result": {"企业名称": "企查查科技股份有限公司"},
        }
        with mock.patch("run_query.query_basic_details", return_value=basic_result) as mock_basic:
            result = run_query.execute_query(
                "企查查科技股份有限公司",
                "2",
                client=object(),
                confirm_expensive=True,
                original_request="查企业基本信息",
            )

        self.assertTrue(mock_basic.called)
        self.assertEqual(result["detail_api"], "2001")
        self.assertEqual(result["request"], "查企业基本信息")

    def test_confirm_expensive_for_enhanced_original_request_executes_2001(self) -> None:
        basic_result = {
            "api_title": "企业信息核验",
            "query": {"company_name": "企查查科技股份有限公司"},
            "has_result": True,
            "result": {"企业名称": "企查查科技股份有限公司", "人员规模": "100-499人"},
        }
        with mock.patch("run_query.query_basic_details", return_value=basic_result) as mock_basic:
            result = run_query.execute_query(
                "企查查科技股份有限公司",
                "确认查询",
                client=object(),
                original_request="查人员规模和参保人数",
            )

        self.assertTrue(mock_basic.called)
        self.assertEqual(result["detail_api"], "2001")
        self.assertEqual(result["request"], "查人员规模和参保人数")
        self.assertIn("人员规模：**100-499人**", result["report_markdown"])

    def test_confirm_expensive_flag_without_detail_api_executes_2001(self) -> None:
        basic_result = {
            "api_title": "企业信息核验",
            "query": {"company_name": "企查查科技股份有限公司"},
            "has_result": True,
            "result": {"企业名称": "企查查科技股份有限公司"},
        }
        with mock.patch("run_query.query_basic_details", return_value=basic_result) as mock_basic:
            result = run_query.execute_query(
                "企查查科技股份有限公司",
                "确认查询",
                client=object(),
                confirm_expensive=True,
                original_request="查企业基本信息",
            )

        self.assertTrue(mock_basic.called)
        self.assertEqual(result["detail_api"], "2001")

    def test_partial_name_goes_to_fuzzy_search_first(self) -> None:
        fuzzy_result = {
            "api_title": "企业模糊搜索",
            "query": {"search_key": "杭州飞致云", "page_index": 1},
            "results": [
                {"企业名称": "杭州飞致云信息科技有限公司", "法定代表人": "阮志敏", "企业状态": "存续"},
                {"企业名称": "杭州飞致云网络科技有限公司", "法定代表人": "王某", "企业状态": "存续"},
            ],
        }
        with mock.patch("run_query.query_fuzzy_search", return_value=fuzzy_result) as mock_fuzzy, mock.patch(
            "run_query.query_basic_details", side_effect=AssertionError("should not call")
        ), mock.patch("run_query.query_registration_details", side_effect=AssertionError("should not call")):
            result = run_query.execute_query("杭州飞致云", "查下基本信息", client=object())

        self.assertTrue(mock_fuzzy.called)
        self.assertEqual(result["mode"], "clarification")
        self.assertEqual([item["script"] for item in result["routes"]], ["fuzzy_search.py"])
        self.assertIn("你确认企业全称后，我会再让你选择走 `410` 还是 `2001`", result["report_markdown"])

    def test_clue_query_routes_directly_to_fuzzy_search(self) -> None:
        fuzzy_result = {
            "api_title": "企业模糊搜索",
            "query": {"search_key": "010-62621818", "page_index": 1},
            "results": [{"企业名称": "企查查科技股份有限公司", "法定代表人": "唐某", "企业状态": "存续"}],
        }
        with mock.patch("run_query.query_fuzzy_search", return_value=fuzzy_result), mock.patch(
            "run_query.query_basic_details", side_effect=AssertionError("should not call")
        ), mock.patch("run_query.query_registration_details", side_effect=AssertionError("should not call")):
            result = run_query.execute_query("010-62621818", "通过电话找企业", client=object())

        self.assertEqual(result["mode"], "clarification")
        self.assertEqual([item["script"] for item in result["routes"]], ["fuzzy_search.py"])
        self.assertIn("企查查科技股份有限公司", result["report_markdown"])

    def test_2001_report_keeps_enhanced_fields(self) -> None:
        basic_result = {
            "api_title": "企业信息核验",
            "query": {"company_name": "杭州飞致云信息科技有限公司"},
            "has_result": True,
            "result": {
                "企业名称": "杭州飞致云信息科技有限公司",
                "统一社会信用代码": "91330106311245339J",
                "法定代表人": "阮志敏",
                "登记状态": "存续",
                "企业性质": "大陆企业",
                "人员规模": "100-499人",
                "参保人数": "215",
                "更多邮箱": "bd@fit2cloud.com",
                "国标行业": "软件开发",
            },
        }
        with mock.patch("run_query.query_basic_details", return_value=basic_result), mock.patch(
            "run_query.query_registration_details", side_effect=AssertionError("should not call")
        ), mock.patch("run_query.query_fuzzy_search", side_effect=AssertionError("should not call")):
            result = run_query.execute_query(
                "杭州飞致云信息科技有限公司",
                "查企业基本信息",
                client=object(),
                detail_api="2001",
                confirm_expensive=True,
            )

        self.assertIn("人员规模：**100-499人**", result["report_markdown"])
        self.assertIn("参保人数：**215**", result["report_markdown"])
        self.assertIn("更多邮箱：**bd@fit2cloud.com**", result["report_markdown"])

    def test_410_request_for_enhanced_field_adds_warning(self) -> None:
        registration_result = {
            "api_title": "企业工商信息",
            "query": {"company_name": "杭州飞致云信息科技有限公司"},
            "has_result": True,
            "result": {
                "企业名称": "杭州飞致云信息科技有限公司",
                "统一社会信用代码": "91330106311245339J",
                "法定代表人": "阮志敏",
                "登记状态": "存续",
            },
        }
        with mock.patch("run_query.query_registration_details", return_value=registration_result), mock.patch(
            "run_query.query_basic_details", side_effect=AssertionError("should not call")
        ), mock.patch("run_query.query_fuzzy_search", side_effect=AssertionError("should not call")):
            result = run_query.execute_query("杭州飞致云信息科技有限公司", "查参保人数", client=object(), detail_api="410")

        self.assertIn("建议改用 2001 企业信息核验", result["report_markdown"])


class AgentPromptTest(unittest.TestCase):
    def test_default_prompt_mentions_credentials_and_expensive_confirmation(self) -> None:
        prompt_file = Path(__file__).resolve().parents[1] / "agents" / "openai.yaml"
        content = prompt_file.read_text(encoding="utf-8")
        self.assertIn("ask the user for QCC Key and QCC SecretKey", content)
        self.assertIn("persist them into qcc-enterprise-query/.env", content)
        self.assertIn("choose 410 or 2001", content)
        self.assertIn("confirm again before calling 2001", content)
        self.assertIn("886", content)


if __name__ == "__main__":
    unittest.main()
