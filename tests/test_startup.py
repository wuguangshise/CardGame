"""Launch from a different working directory, as IDEs and shortcuts may do."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import io

ROOT = Path(__file__).resolve().parents[1]


class Startup(unittest.TestCase):
    def run_script(self, script, *args):
        with tempfile.TemporaryDirectory() as directory:
            return subprocess.run([sys.executable, str(ROOT / script), *args],
                                  cwd=directory, input='', capture_output=True, text=True,
                                  encoding='utf-8', timeout=15)

    def test_old_console_help(self):
        result = self.run_script('play.py', '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--hotseat', result.stdout)

    def test_old_gui_help(self):
        result = self.run_script('play_gui.py', '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--no-timer', result.stdout)

    def test_new_launcher_forwards_arguments(self):
        for args, expected in [(('--help',), '--no-timer'), (('--cli', '--help'), '--hotseat')]:
            result = self.run_script('start.py', *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)

    def test_console_diagnostic_and_no_stdin(self):
        result = self.run_script('start.py', '--cli', '--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('检查通过', result.stdout)
        result = self.run_script('play.py', '--seed', '4')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('没有可用输入', result.stdout)

    def test_error_report_preserves_traceback_and_install_hint(self):
        import startup
        with tempfile.TemporaryDirectory() as directory, patch.object(startup, 'ROOT', Path(directory)), \
                patch.object(startup, 'pause_if_double_clicked'), patch('sys.stderr', new_callable=io.StringIO) as output:
            exc = ModuleNotFoundError("No module named 'pygame'")
            startup.report_error(type(exc), exc, None)
            self.assertIn('pip install', output.getvalue())
            self.assertIn(sys.executable, output.getvalue())
            self.assertIn('pygame', (Path(directory) / 'logs/startup_error.log').read_text())
