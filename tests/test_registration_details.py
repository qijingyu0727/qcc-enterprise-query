from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import registration_details


class RegistrationDetailsNormalizeTest(unittest.TestCase):
    def test_normalize_registration_details_maps_410_fields(self) -> None:
        payload = {
            "Result": {
                "Name": "杭州飞致云信息科技有限公司",
                "CreditCode": "91330106311245339J",
                "OperName": "阮志敏",
                "Status": "存续",
                "StartDate": "2014-10-24 00:00:00",
                "RegistCapi": "1000万元",
                "EconKind": "有限责任公司",
                "Address": "浙江省杭州市西湖区山景路7号",
                "Scope": "软件开发；技术服务。",
                "TermStart": "2014-10-24 00:00:00",
                "TermEnd": "2044-10-23 00:00:00",
                "BelongOrg": "杭州市西湖区市场监督管理局",
                "CheckDate": "2024-06-01 00:00:00",
                "IsOnStock": "1",
                "StockType": "科创板",
                "StockNumber": "688999",
                "Area": {
                    "Province": "浙江省",
                    "City": "杭州市",
                    "County": "西湖区",
                },
            }
        }

        result = registration_details.normalize_registration_details(payload)

        self.assertEqual(result["企业名称"], "杭州飞致云信息科技有限公司")
        self.assertEqual(result["所属地区"], "浙江省 / 杭州市 / 西湖区")
        self.assertEqual(result["营业期限"], "2014-10-24 至 2044-10-23")
        self.assertEqual(result["上市状态"], "已上市 / 科创板 / 688999")

    def test_markdown_report_uses_grouped_sections(self) -> None:
        output = {
            "api_title": "企业工商信息",
            "query": {"company_name": "杭州飞致云信息科技有限公司"},
            "has_result": True,
            "result": {
                "企业名称": "杭州飞致云信息科技有限公司",
                "统一社会信用代码": "91330106311245339J",
                "经营范围": "软件开发；技术服务。",
            },
        }

        markdown = registration_details.format_markdown_report(output)

        self.assertIn("## 核心结论", markdown)
        self.assertIn("## 经营与地址", markdown)
        self.assertIn("软件开发；技术服务。", markdown)


if __name__ == "__main__":
    unittest.main()
