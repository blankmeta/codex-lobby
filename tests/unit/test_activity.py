import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from codex_switch.domain.activity import Activity, Action, ModelStep, Tokens, classify, command_category
from codex_switch.infrastructure.activity_logs import LogParser, LogTail, SessionFollower, SessionTree, safe_text
from codex_switch.infrastructure.virtual_screen import VirtualScreen
from codex_switch.infrastructure.live_runner import InputRouter, LiveRunner, layout
from codex_switch.domain.models import Preferences
from codex_switch.presentation.activity import panel_lines


def codex(kind,payload,t='2026-09-22T12:00:00Z'):
    return {'type':kind,'payload':payload,'timestamp':t}


class ClassificationTests(unittest.TestCase):
    def test_command_corpus(self):
        corpus = {
            'rg --files':'search','cat file.py':'read','sed -n 1,10p a.py':'read','sed -i s/a/b/ a.py':'edit',
            'git diff --stat':'git','gh run view 123 --json status':'ci','gh pr checks 12':'ci',
            'gh pr create --title test':'git','glab ci status':'ci','python3 -m unittest discover':'test',
            'PYTHONPATH=src /tmp/venv/bin/python -m pytest':'test','npm run test':'test','npm run build':'build',
            'cargo clippy':'build','go test ./...':'test','dotnet test':'test','pip install a':'environment',
            'uv run pytest':'test','curl https://example.org':'web','sleep 1':'wait',
            'cat a; git status':'mixed','git status; echo done':'git','python script.py':'execute',
            'echo "pytest"':'execute','python -c "print(\"gh run view\")"':'execute',
            "python - <<'PY'\nprint('pytest')\nPY":'execute',
            'unknown-program --test --gh-run-view':'execute',
            'pwsh -Command "Get-Content x"':'read',
        }
        for command,expected in corpus.items():
            with self.subTest(command=command): self.assertEqual(command_category(command),expected)
        self.assertEqual(command_category(['/bin/zsh','-lc','gh run view 123']), 'ci')

    def test_provider_names_and_unknown_mcp(self):
        for name,category in [('Read','read'),('Edit','edit'),('Glob','search'),('Task','agent'),('TodoWrite','plan'),('web__run','web'),('unknown','other')]:
            self.assertEqual(classify(name),category)

    def test_mixed_steps_do_not_double_count_tokens(self):
        activity=Activity(actions={'a':Action('a','Read','read'),'b':Action('b','Edit','edit')},steps={'s':ModelStep('s',Tokens(100,20,70,0,5),['a','b'])})
        rows=activity.totals()
        self.assertEqual(sum(r['tokens'] for r in rows),120)
        self.assertEqual(next(r['tokens'] for r in rows if r['category']=='mixed'),120)
        self.assertEqual(sum(r['calls'] for r in rows),2)


class LogTests(unittest.TestCase):
    def test_resumed_turn_prefers_modern_usage_despite_different_lifetime_totals(self):
        p=LogParser('codex')
        p.feed(codex('event_msg',{'type':'task_started','turn_id':'old'}))
        legacy=lambda total,last: codex('event_msg',{'type':'token_count','info':{'total_token_usage':{'input_tokens':total},'last_token_usage':{'input_tokens':last}}})
        p.feed(legacy(10,10))
        p.feed(codex('event_msg',{'type':'task_started','turn_id':'new'}))
        # Legacy arrives before modern in this synthetic turn; replace it too.
        p.feed(legacy(20,20))
        p.feed(codex('token_usage_record',{'turn_id':'new','response_id':'r','usage':{'input_tokens':20},'thread_token_usage':{'input_tokens':500020}}))
        p.feed(legacy(999020,20))
        self.assertEqual(p.snapshot().tokens.total,30)
        # A subsequent run with a legacy-only CLI still contributes new usage.
        p.feed(codex('event_msg',{'type':'task_started','turn_id':'older-cli'}))
        p.feed(legacy(999060,40))
        self.assertEqual(p.snapshot().tokens.total,70)

    def test_repetition_uses_all_arguments_without_exposing_them(self):
        p = LogParser('codex')
        for key,path in [('a','first.py'),('b','second.py'),('c','first.py')]:
            p._action(key,'Read',{'file_path':path},1)
            p._result(key,'same content',2)
        self.assertNotEqual(p.activity.actions['a'].fingerprint,p.activity.actions['b'].fingerprint)
        self.assertEqual(p.activity.actions['a'].fingerprint,p.activity.actions['c'].fingerprint)

    def test_session_tree_deduplicates_copied_history_and_follows_children(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder); directory=home/'sessions'; directory.mkdir()
            shared=codex('event_msg',{'type':'token_count','info':{'total_token_usage':{'input_tokens':100},'last_token_usage':{'input_tokens':100}}})
            def write(name,identity,parent=None,records=()):
                meta={'id':identity,'cwd':folder}
                if parent: meta['source']={'subagent':{'thread_spawn':{'parent_thread_id':parent}}}
                path=directory/name
                path.write_text('\n'.join(json.dumps(r) for r in [codex('session_meta',meta),*records])+'\n')
                return path
            root=write('root.jsonl','root',records=[shared])
            child=write('child.jsonl','child','root',[shared,codex('token_usage_record',{'response_id':'child-r','usage':{'input_tokens':20}})])
            write('unrelated.jsonl','unrelated',records=[codex('token_usage_record',{'response_id':'other-r','usage':{'input_tokens':999}})])
            tree=SessionTree(LogTail(root,'codex'),home)
            report=tree.poll()
            self.assertEqual(report.tokens.total,120)
            self.assertEqual(report.subagents,1)
            with child.open('a') as f:
                f.write(json.dumps(codex('token_usage_record',{'response_id':'next-r','usage':{'input_tokens':30}},'2026-09-22T12:00:02Z'))+'\n')
            updated=tree.poll()
            self.assertEqual(updated.tokens.total,150)
            self.assertGreater(updated.updated_at,report.updated_at)

    def test_claude_child_logs_are_local_to_the_selected_session(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder); project=home/'projects'/'demo'; project.mkdir(parents=True)
            root=project/'root.jsonl';root.write_text('{}\n')
            sub=project/'root'/'subagents';sub.mkdir(parents=True)
            (sub/'agent.jsonl').write_text(json.dumps({'type':'assistant','sessionId':'root','message':{'id':'m','usage':{'input_tokens':10},'content':[]}})+'\n')
            report=SessionTree(LogTail(root,'claude'),home).poll()
            self.assertEqual(report.tokens.total,10)
            self.assertEqual(report.subagents,1)

    def test_modern_codex_nested_operations_and_duplicate_usage(self):
        p=LogParser('codex');usage={'input_tokens':100,'output_tokens':20,'cached_input_tokens':70,'reasoning_output_tokens':5}
        records=[
            codex('response_item',{'type':'custom_tool_call','name':'exec','call_id':'outer','input':'not executed'}),
            codex('token_usage_record',{'response_id':'r','usage':usage,'thread_token_usage':usage}),
            codex('event_msg',{'type':'item_completed','item':{'type':'CommandExecution','id':'inner','command':['zsh','-lc','gh run view 123'],'duration':{'secs':2,'nanos':0},'status':'completed','exit_code':0,'aggregated_output':'in_progress'}}),
            codex('response_item',{'type':'custom_tool_call_output','call_id':'outer','output':'wrapped output'}),
            codex('event_msg',{'type':'token_count','info':{'total_token_usage':usage,'last_token_usage':usage}}),
        ]
        for r in records: p.feed(r)
        p.feed(records[1]); p.feed(records[2])
        report=p.snapshot()
        self.assertEqual(report.tokens.total,120)
        self.assertEqual(list(report.actions),['inner'])
        self.assertEqual(report.totals()[0]['category'],'ci')
        self.assertEqual(report.totals()[0]['tokens'],120)
        self.assertEqual(report.totals()[0]['seconds'],2)

    def test_claude_duplicate_message_blocks_and_cache(self):
        p=LogParser('claude');usage={'input_tokens':10,'output_tokens':3,'cache_read_input_tokens':50,'cache_creation_input_tokens':20}
        row={'type':'assistant','timestamp':'2026-09-22T12:00:00Z','message':{'id':'msg','usage':usage,'content':[{'type':'tool_use','id':'a','name':'Bash','input':{'command':'pytest'}}]}}
        p.feed(row);p.feed(row)
        row['message']['usage']['output_tokens']=8;p.feed(row)
        p.feed({'type':'user','timestamp':'2026-09-22T12:00:04Z','message':{'content':[{'type':'tool_result','tool_use_id':'a','content':'ok'}]}})
        report=p.snapshot()
        self.assertEqual(report.tokens.total,88)
        self.assertEqual(report.tokens.cached,50)
        self.assertEqual(len(report.actions),1)
        self.assertEqual(report.actions['a'].seconds,4)

    def test_tail_is_incremental_partial_lines_and_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'log.jsonl';path.write_bytes(b'')
            tail=LogTail(path,'codex')
            record=json.dumps(codex('token_usage_record',{'response_id':'a','usage':{'input_tokens':5}})).encode()
            path.write_bytes(record)
            self.assertIsNone(tail.poll().tokens)
            with path.open('ab') as f:f.write(b'\n')
            self.assertEqual(tail.poll().tokens.total,5)
            self.assertEqual(tail.poll().tokens.total,5)
            path.write_text('garbage\n')
            self.assertIsNone(tail.poll().tokens)
            self.assertEqual(tail.poll().malformed,1)

    def test_two_simultaneous_sessions_require_selection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'sessions').mkdir()
            follower=SessionFollower(root,'codex')
            for name in ('a','b'):
                (root/'sessions'/f'{name}.jsonl').write_text(json.dumps(codex('session_meta',{'id':name,'cwd':d}))+ '\n')
            self.assertIsNone(follower.poll())
            self.assertTrue(follower.ambiguous)

    def test_text_does_not_expose_common_secrets_or_terminal_controls(self):
        text=safe_text('\x1b[31mhi Bearer secret123 access_token=private vless://password@host\x1b[0m')
        self.assertNotIn('secret123',text);self.assertNotIn('access_token=private',text);self.assertNotIn('password@host',text);self.assertNotIn('\x1b',text)


class ScreenTests(unittest.TestCase):
    def test_disabled_monitor_bypasses_the_terminal_wrapper(self):
        settings=SimpleNamespace(load=lambda:Preferences(True,monitor_enabled=False))
        terminal=Mock();run=Mock(return_value=SimpleNamespace(returncode=0))
        env={'TERM':'xterm-256color'}
        with patch('sys.stdin.isatty',return_value=True), patch('sys.stdout.isatty',return_value=True), patch('codex_switch.infrastructure.live_runner.spawn_terminal') as spawn:
            LiveRunner(settings,terminal,runner=run)(['codex'],env=env,pass_fds=(17,))
        run.assert_called_once_with(['codex'],env=env,pass_fds=(17,))
        spawn.assert_not_called();terminal.session.assert_not_called()

    def test_alternate_screen_unicode_and_terminal_replies(self):
        replies=[];s=VirtualScreen(20,5,replies.append)
        s.feed('Привет 界'.encode());before=s.primary.display[:]
        s.feed(b'\x1b[?1049hOTHER\x1b[6n')
        self.assertIn(b'\x1b[1;6R',replies)
        self.assertTrue(s.current.display[0].startswith('OTHER'))
        s.feed(b'\x1b[?1049l')
        self.assertEqual(s.primary.display,before)
        s.resize(6,30);self.assertEqual(s.current.columns,30)

    def test_fragmented_input_and_paste_do_not_trigger_shortcuts(self):
        r=InputRouter()
        self.assertEqual(r.feed(b'\x1b[1'),(b'',[]))
        self.assertEqual(r.feed(b'9~'),(b'',['toggle']))
        paste=b'\x1b[200~hello\x1b[19~\x03\x1b[201~'
        self.assertEqual(r.feed(paste),(paste,[]))
        self.assertEqual(r.feed(b'\x03'),(b'\x03',[]))

    def test_panel_is_twenty_percent_and_unknown_is_not_zero(self):
        self.assertEqual(layout(120,30),(95,30,24))
        self.assertEqual(layout(120,30,False),(120,30,0))
        lines=panel_lines(Activity(),24,30)
        self.assertTrue(any('Tokens —' in line for line in lines))
