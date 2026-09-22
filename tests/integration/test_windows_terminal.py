"""Native Win32 console events and mode restoration, exercised in Windows CI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.name == "nt", "Native Windows console")
class WindowsTerminalTests(unittest.TestCase):
    def test_arrow_enter_and_escape_restore_console_modes(self):
        program = r'''
import ctypes,json,sys,threading,time
from ctypes import wintypes
from pathlib import Path
from codex_switch.infrastructure.platforms.windows import WindowsTerminal,kernel
from codex_switch.presentation.console import Console
from codex_switch.presentation.menu import TerminalMenu,Option
api=kernel()
sys.stdin=open('CONIN$','r',encoding='utf-8')
sys.stdout=open('CONOUT$','w',encoding='utf-8')
class Char(ctypes.Union):
    _fields_=[('UnicodeChar',wintypes.WCHAR),('AsciiChar',ctypes.c_char)]
class Key(ctypes.Structure):
    _fields_=[('down',wintypes.BOOL),('repeat',wintypes.WORD),('vk',wintypes.WORD),('scan',wintypes.WORD),('char',Char),('state',wintypes.DWORD)]
class Event(ctypes.Union):
    _fields_=[('key',Key),('padding',ctypes.c_byte*16)]
class Input(ctypes.Structure):
    _fields_=[('type',wintypes.WORD),('event',Event)]
api.WriteConsoleInputW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Input),wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
def modes():
    result=[]
    for number in (-10,-11):
        mode=wintypes.DWORD()
        assert api.GetConsoleMode(api.GetStdHandle(number),ctypes.byref(mode))
        result.append(mode.value)
    return result
def send(vk,scan,char):
    event=Input();event.type=1
    event.event.key=Key(True,1,vk,scan,Char(UnicodeChar=char),0)
    written=wintypes.DWORD()
    assert api.WriteConsoleInputW(api.GetStdHandle(-10),ctypes.byref(event),1,ctypes.byref(written))
def keys():
    time.sleep(.3);send(40,80,chr(0))
    time.sleep(.2);send(13,28,chr(13))
    time.sleep(.3);send(27,1,chr(27))
before=modes()
thread=threading.Thread(target=keys);thread.start()
picker=TerminalMenu(Console(terminal=WindowsTerminal()))
options=[Option('codex','Codex'),Option('claude','Claude')]
first=picker.choose('RunLobby',options)
second=picker.choose('RunLobby',options)
thread.join()
Path(sys.argv[1]).write_text(json.dumps({'first':first,'second':second,'restored':modes()==before}))
'''
        with tempfile.TemporaryDirectory() as folder:
            result_file = Path(folder) / "result.json"
            root = Path(__file__).parents[2]
            env = {**os.environ, "PYTHONPATH": str(root / "src"), "TERM": "xterm-256color"}
            process = subprocess.Popen([sys.executable, "-c", program, str(result_file)],
                                       env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
            try:
                self.assertEqual(process.wait(timeout=20), 0)
                self.assertEqual(json.loads(result_file.read_text()), {"first": "claude", "second": None, "restored": True})
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
