from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import basic_details


class BasicDetailsNormalizeTest(unittest.TestCase):
    def test_normalize_basic_details_maps_verify_fields(self) -> None:
        payload = {
            "Result": {
                "VerifyResult": 1,
                "Data": {
                    "Name": "杭州飞致云信息科技有限公司",
                    "CreditCode": "91330106311245339J",
                    "OperName": "阮志敏",
                    "Status": "存续",
                    "StartDate": "2014-10-24 00:00:00",
                    "RegisteredCapital": "1000",
                    "RegisteredCapitalUnit": "万元",
                    "RegisteredCapitalCCY": "人民币",
                    "EconKind": "有限责任公司",
                    "EntType": "0",
                    "PersonScope": "100-499人",
                    "InsuredCount": "215",
                    "Scale": "M",
                    "Address": "浙江省杭州市西湖区山景路7号",
                    "Scope": "软件开发；技术服务。",
                    "TermStart": "2014-10-24 00:00:00",
                    "TermEnd": "2044-10-23 00:00:00",
                    "BelongOrg": "杭州市西湖区市场监督管理局",
                    "CheckDate": "2024-06-01 00:00:00",
                    "Area": {
                        "Province": "浙江省",
                        "City": "杭州市",
                        "County": "西湖区",
                    },
                    "Industry": {
                        "Industry": "信息传输、软件和信息技术服务业",
                        "SubIndustry": "软件和信息技术服务业",
                        "MiddleCategory": "软件开发",
                        "SmallCategory": "应用软件开发",
                    },
                    "ContactInfo": {
                        "Tel": "0571-12345678",
                        "Email": "hello@fit2cloud.com",
                        "WebSiteList": [{"Url": "https://www.fit2cloud.com"}],
                        "MoreEmailList": [
                            {"Email": "bd@fit2cloud.com"},
                            {"Email": "bd@fit2cloud.com"},
                            {"Email": "sales@fit2cloud.com"},
                        ],
                        "MoreTelList": [
                            {"Tel": "400-800-1234"},
                            {"Tel": "400-800-1234"},
                        ],
                    },
                    "StockInfo": {
                        "StockNumber": "688999",
                        "StockType": "科创板",
                    },
                },
            }
        }

        result = basic_details.normalize_basic_details(payload)

        self.assertEqual(result["企业名称"], "杭州飞致云信息科技有限公司")
        self.assertEqual(result["企业性质"], "大陆企业")
        self.assertEqual(result["企业规模"], "100-499人")
        self.assertEqual(result["人员规模"], "100-499人")
        self.assertEqual(result["所属地区"], "浙江省 / 杭州市 / 西湖区")
        self.assertEqual(
            result["国标行业"],
            "信息传输、软件和信息技术服务业 / 软件和信息技术服务业 / 软件开发 / 应用软件开发",
        )
        self.assertEqual(result["更多邮箱"], "bd@fit2cloud.com；sales@fit2cloud.com")
        self.assertEqual(result["电话"], "0571-12345678")
        self.assertEqual(result["更多电话"], "400-800-1234")
        self.assertEqual(result["邮箱"], "hello@fit2cloud.com")
        self.assertEqual(result["网址"], "https://www.fit2cloud.com")
        self.assertEqual(result["营业期限"], "2014-10-24 至 2044-10-23")
        self.assertEqual(
            result["联系信息"],
            "电话：0571-12345678；更多电话：400-800-1234；邮箱：hello@fit2cloud.com；网址：https://www.fit2cloud.com",
        )
        self.assertEqual(result["上市状态"], "已上市 / 科创板 / 688999")

    def test_normalize_basic_details_skips_empty_nested_fields(self) -> None:
        payload = {
            "Data": {
                "Name": "测试企业",
                "CreditCode": "91330106311245339J",
                "ContactInfo": {},
                "Industry": {},
                "Area": {},
            }
        }

        result = basic_details.normalize_basic_details(payload)

        self.assertEqual(result["企业名称"], "测试企业")
        self.assertNotIn("联系信息", result)
        self.assertNotIn("更多邮箱", result)
        self.assertNotIn("国标行业", result)
        self.assertNotIn("所属地区", result)

    def test_markdown_report_uses_grouped_sections(self) -> None:
        output = {
            "api_title": "企业信息核验",
            "query": {"company_name": "杭州飞致云信息科技有限公司"},
            "has_result": True,
            "result": {
                "企业名称": "杭州飞致云信息科技有限公司",
                "企业性质": "大陆企业",
                "参保人数": "215",
                "联系信息": "电话：0571-12345678",
            },
        }

        markdown = basic_details.format_markdown_report(output)

        self.assertIn("## 核心结论", markdown)
        self.assertIn("## 行业与经营范围", markdown)
        self.assertIn("**215**", markdown)


if __name__ == "__main__":
    unittest.main()
