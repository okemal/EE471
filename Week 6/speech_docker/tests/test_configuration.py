"""Check credential isolation and the local configuration helper offline."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configure import read_config, write_config


class ConfigurationTests(unittest.TestCase):
    def test_only_azure_fields_are_extracted_with_canonical_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.env"
            source.write_text(
                "UNRELATED_TOKEN='do-not-copy'\n"
                "export AZURE_API_KEY_1=legacy-key\n"
                "AZURE_SPEECH_KEY='test-secret' # comment\n"
                'AZURE_SPEECH_REGION="eastus"\n', encoding="utf-8"
            )
            key, region = read_config(source)
            self.assertEqual((key, region), ("test-secret", "eastus"))
            dest = Path(tmp) / "output"
            dest.mkdir()
            write_config(dest, key, region)
            self.assertEqual((dest / ".secrets/azure_speech_key").read_text(), "test-secret\n")
            self.assertNotIn("test-secret", (dest / ".env").read_text())
            self.assertNotIn("do-not-copy", "".join(p.read_text() for p in dest.rglob("*") if p.is_file()))
            self.assertEqual((dest / ".secrets").stat().st_mode & 0o777, 0o700)

    def test_legacy_key_and_empty_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            source = dest / "source.env"
            source.write_text("AZURE_API_KEY_1=legacy-key\nAZURE_SPEECH_REGION=eastus\n")
            self.assertEqual(read_config(source), ("legacy-key", "eastus"))
            write_config(dest, "", "", unconfigured=True)
            self.assertEqual((dest / ".secrets/azure_speech_key").read_text(), "")
            with self.assertRaises(ValueError):
                write_config(dest, "replacement", "eastus")
            write_config(dest, "replacement", "eastus", force=True)

    def test_bad_values_do_not_appear_in_errors_or_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for key, region in [("secret\nINJECT=true", "eastus"), ("test-secret", "https://evil.invalid")]:
                with self.assertRaises(ValueError) as error:
                    write_config(Path(tmp), key, region)
                self.assertNotIn(key, str(error.exception))
                self.assertNotIn(region, str(error.exception))
            self.assertFalse((Path(tmp) / ".env").exists())

    def test_shell_syntax_is_never_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.env"
            source.write_text("AZURE_SPEECH_KEY='$(touch sentinel)'\nAZURE_SPEECH_REGION=eastus\n")
            key, region = read_config(source)
            with self.assertRaises(ValueError):
                write_config(Path(tmp), key, region)
            self.assertFalse((Path(tmp) / "sentinel").exists())


if __name__ == "__main__":
    unittest.main()
