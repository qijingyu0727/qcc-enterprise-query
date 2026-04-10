from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import qcc_client


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class QccClientTest(unittest.TestCase):
    def test_compute_token_uses_uppercase_md5(self) -> None:
        token = qcc_client.compute_token("demo", "secret", "1700000000")
        self.assertEqual(token, "E1511CFB8334A2E90E762CA5289B304A")

    def test_build_headers_include_token_and_timespan(self) -> None:
        client = qcc_client.QccOpenApiClient("demo", "secret")
        headers = client.build_headers(timespan="1700000000")
        self.assertEqual(headers["Timespan"], "1700000000")
        self.assertEqual(headers["Token"], "E1511CFB8334A2E90E762CA5289B304A")

    def test_resolve_credentials_raises_without_env_or_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            with mock.patch.dict("os.environ", {}, clear=True):
                with self.assertRaises(qcc_client.QccApiError):
                    qcc_client.resolve_credentials(env_path=env_path)

    def test_resolve_credentials_reads_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("QCC_KEY=file-key\nQCC_SECRET_KEY=file-secret\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {}, clear=True):
                app_key, secret_key = qcc_client.resolve_credentials(env_path=env_path)

        self.assertEqual(app_key, "file-key")
        self.assertEqual(secret_key, "file-secret")

    def test_process_env_has_priority_over_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("QCC_KEY=file-key\nQCC_SECRET_KEY=file-secret\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {"QCC_KEY": "env-key", "QCC_SECRET_KEY": "env-secret"}, clear=True):
                app_key, secret_key = qcc_client.resolve_credentials(env_path=env_path)

        self.assertEqual(app_key, "env-key")
        self.assertEqual(secret_key, "env-secret")

    def test_write_credentials_preserves_other_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("# demo\nOTHER_VAR=keep-me\nQCC_KEY=old-key\n", encoding="utf-8")

            status = qcc_client.write_credentials_to_env("new-key", "new-secret", env_path=env_path)
            content = env_path.read_text(encoding="utf-8")

        self.assertIn("OTHER_VAR=keep-me", content)
        self.assertIn("QCC_KEY=new-key", content)
        self.assertIn("QCC_SECRET_KEY=new-secret", content)
        self.assertTrue(status["has_credentials"])
        self.assertEqual(status["source_summary"], "env_file")

    def test_get_uses_expected_query_parameter_for_verify_api(self) -> None:
        payload = {"Status": "200", "Message": "查询成功", "Data": {"Name": "企查查科技股份有限公司"}}
        with mock.patch("qcc_client.request.urlopen", return_value=FakeResponse(payload)) as mock_urlopen:
            client = qcc_client.QccOpenApiClient("demo", "secret")
            result = client.get(qcc_client.BASIC_DETAILS_API, "企查查科技股份有限公司")

        self.assertEqual(result["Data"]["Name"], "企查查科技股份有限公司")
        request_obj = mock_urlopen.call_args.args[0]
        parsed = urlparse(request_obj.full_url)
        query = parse_qs(parsed.query)
        self.assertEqual(query["key"], ["demo"])
        self.assertEqual(query["searchKey"], ["企查查科技股份有限公司"])

    def test_get_uses_expected_query_parameter_for_registration_api(self) -> None:
        payload = {"Status": "200", "Message": "查询成功", "Result": {"Name": "企查查科技股份有限公司"}}
        with mock.patch("qcc_client.request.urlopen", return_value=FakeResponse(payload)) as mock_urlopen:
            client = qcc_client.QccOpenApiClient("demo", "secret")
            client.get(qcc_client.REGISTRATION_DETAILS_API, "企查查科技股份有限公司")

        request_obj = mock_urlopen.call_args.args[0]
        parsed = urlparse(request_obj.full_url)
        query = parse_qs(parsed.query)
        self.assertEqual(query["keyword"], ["企查查科技股份有限公司"])

    def test_business_error_raises(self) -> None:
        payload = {"Status": "500", "Message": "余额不足"}
        with mock.patch("qcc_client.request.urlopen", return_value=FakeResponse(payload)):
            client = qcc_client.QccOpenApiClient("demo", "secret")
            with self.assertRaises(qcc_client.QccApiError):
                client.get(qcc_client.FUZZY_SEARCH_API, "企查查科技")


if __name__ == "__main__":
    unittest.main()
