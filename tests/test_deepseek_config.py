"""The release only accepts official DeepSeek configuration."""

import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


class DeepSeekConfigTest(unittest.TestCase):
    def load_config(self, values):
        with patch.dict(os.environ, values, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(str(Path(__file__).resolve().parents[1] / "config.py"))

    def test_legacy_credentials_and_endpoint_overrides_are_ignored(self):
        config = self.load_config(
            {
                "SILICONFLOW_API_KEY": "legacy-test-key",
                "SILICONFLOW_API_URL": "https://example.com/chat/completions",
                "SILICONFLOW_MODEL_NAME": "legacy-model",
                "DEEPSEEK_API_URL": "https://example.com/chat/completions",
            }
        )
        self.assertEqual(config["API_KEY"], "")
        self.assertEqual(config["API_URL"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(config["MODEL_NAME"], "deepseek-flash")
        self.assertEqual(config["AUTOCOMPLETE_MODEL_NAME"], "deepseek-flash")

    def test_official_key_and_model_configuration(self):
        config = self.load_config(
            {
                "DEEPSEEK_API_KEY": "official-test-key",
                "DEEPSEEK_MODEL_NAME": "deepseek-v4-pro",
                "DEEPSEEK_AUTOCOMPLETE_MODEL_NAME": "deepseek-flash",
            }
        )
        self.assertEqual(config["API_KEY"], "official-test-key")
        self.assertEqual(config["MODEL_NAME"], "deepseek-v4-pro")
        self.assertEqual(config["AUTOCOMPLETE_MODEL_NAME"], "deepseek-flash")
