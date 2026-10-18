"""Configuration behavior is identical for native Python and containers."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from salesbench.config import load_environment


class ConfigTests(unittest.TestCase):
    def test_env_file_loads_without_overwriting_container_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'.env'
            path.write_text('DATABASE_URL=file-db\nLLM_MODEL=file-model\n',encoding='utf-8')
            with patch.dict(os.environ,{'DATABASE_URL':'container-db'},clear=True):
                load_environment(path)
                self.assertEqual(os.environ['DATABASE_URL'],'container-db')
                self.assertEqual(os.environ['LLM_MODEL'],'file-model')

    def test_values_are_data_not_shell_commands_or_variable_expansion(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'.env'
            path.write_text('OPENAI_API_KEY="literal-${UNCHANGED}-$(not-a-command)"\n',encoding='utf-8')
            with patch.dict(os.environ,{},clear=True):
                load_environment(path)
                self.assertEqual(os.environ['OPENAI_API_KEY'],'literal-${UNCHANGED}-$(not-a-command)')

    def test_missing_file_is_optional(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(load_environment(Path(folder)/'missing.env'))


if __name__=='__main__':
    unittest.main()
