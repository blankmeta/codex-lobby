import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CLIProcessTests(unittest.TestCase):
    def test_clean_first_run_selects_account_and_launches_with_exact_arguments(self):
        root = Path(__file__).parents[2]
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            binaries = directory / "bin"
            binaries.mkdir()
            auth = binaries / "codex-auth"
            auth.write_text(f'''#!{sys.executable}
import json,sys
from pathlib import Path
args=sys.argv[1:]
if args[0]=='list':
 print(json.dumps({{"schema_version":1,"accounts":[{{"account_key":"personal","email":"personal@example.com","active":True}},{{"account_key":"work","email":"work@example.com"}}]}}))
elif args[0]=='switch':
 Path({str(directory / 'selected')!r}).write_text(args[1])
 print(json.dumps({{"schema_version":1,"switched_to":{{"account_key":args[1]}}}}))
''')
            auth.chmod(0o755)
            codex = binaries / "codex"
            codex.write_text(f'''#!{sys.executable}
import json,sys
from pathlib import Path
Path({str(directory / 'args.json')!r}).write_text(json.dumps(sys.argv[1:]))
sys.exit(7)
''')
            codex.chmod(0o755)
            env = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"], "PYTHONPATH": str(root / "src"),
                   "CODEX_SWITCH_HOME": str(directory / "app"), "CODEX_SWITCH_LANG": "en"}
            result = subprocess.run([sys.executable, "-m", "codex_switch", "--", "exec", "an argument with spaces"],
                                    input="1\n2\n", capture_output=True, text=True, env=env, timeout=10)
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            self.assertEqual((directory / "selected").read_text(), "work")
            self.assertEqual(json.loads((directory / "args.json").read_text()), ["exec", "an argument with spaces"])
            self.assertFalse(json.loads((directory / "app/settings.json").read_text())["proxy_enabled"])

    def test_new_install_creates_profile_binds_project_and_emits_json(self):
        root = Path(__file__).parents[2]
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            binaries = directory / "bin"
            binaries.mkdir()
            original = directory / "original"
            original.mkdir()
            (original / "auth.json").write_text('{"untouched":true}')
            auth = binaries / "codex-auth"
            auth.write_text(f'''#!{sys.executable}
import json,os
from pathlib import Path
home=Path(os.environ['CODEX_HOME'])
data=json.loads((home/'auth.json').read_text()) if (home/'auth.json').exists() else {{}}
rows=[{{"account_key":"personal","email":"personal@example.com","active":True}}] if data.get('synthetic') else []
print(json.dumps({{"schema_version":1,"accounts":rows}}))
''')
            auth.chmod(0o755)
            codex = binaries / "codex"
            codex.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
home=Path(os.environ['CODEX_HOME'])
if sys.argv[-1]=='login':
 (home/'auth.json').write_text('{{"synthetic":true}}')
else:
 (home/'last-args.json').write_text(json.dumps(sys.argv[1:]))
 sys.exit(7)
''')
            codex.chmod(0o755)
            env = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"], "PYTHONPATH": str(root / "src"),
                   "CODEX_SWITCH_HOME": str(directory / "app"), "CODEX_HOME": str(original), "CODEX_SWITCH_LANG": "en"}
            def run(*args, input=None):
                return subprocess.run([sys.executable, "-m", "codex_switch", *args], input=input,
                                      capture_output=True, text=True, env=env, cwd=directory, timeout=10)
            launched = run("--", "exec", "argument with spaces", input="1\n")
            self.assertEqual(launched.returncode, 7, launched.stdout + launched.stderr)
            home = directory / "app/profiles/personal"
            self.assertEqual(json.loads((home / "last-args.json").read_text())[-2:], ["exec", "argument with spaces"])
            self.assertEqual(run("bind", "personal").returncode, 0)
            status = run("status", "--json")
            self.assertEqual(status.returncode, 0, status.stderr)
            data = json.loads(status.stdout)
            self.assertEqual(data["project"]["profile"], "personal")
            self.assertEqual(data["profiles"][0]["state"], "ready")
            self.assertEqual((original / "auth.json").read_text(), '{"untouched":true}')
            self.assertEqual(run("legacy", "accounts").returncode, 0)
