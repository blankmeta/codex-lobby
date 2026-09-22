"""Native Win32 leases and console input; no shell or Unix emulation."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
import subprocess
import time


def kernel():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                               wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    api.GetStdHandle.argtypes = [wintypes.DWORD]
    api.GetStdHandle.restype = wintypes.HANDLE
    api.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    api.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    return api


class WindowsLease:
    def __init__(self, handle):
        self.handle = handle

    @contextmanager
    def child_options(self):
        info = subprocess.STARTUPINFO()
        info.lpAttributeList = {"handle_list": [self.handle]}
        os.set_handle_inheritable(self.handle, True)
        try:
            yield {"startupinfo": info, "close_fds": True}
        finally:
            os.set_handle_inheritable(self.handle, False)


class WindowsLocks:
    @contextmanager
    def acquire(self, path, *, wait=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        api = kernel()
        while True:
            # Exclusive sharing persists until the last inherited handle closes,
            # including after the parent wrapper is killed.
            handle = api.CreateFileW(str(path), 0xC0000000, 0, None, 4, 0x80, None)
            if handle != ctypes.c_void_p(-1).value:
                break
            error = ctypes.get_last_error()
            if error not in (32, 33):
                raise ctypes.WinError(error)
            if not wait:
                raise BlockingIOError("Account is already open")
            time.sleep(.05)
        try:
            yield WindowsLease(handle)
        finally:
            api.CloseHandle(handle)


class WindowsTerminal:
    @contextmanager
    def session(self):
        api = kernel()
        handles = [(api.GetStdHandle(-10), wintypes.DWORD()), (api.GetStdHandle(-11), wintypes.DWORD())]
        changed = []
        try:
            for i, (handle, original) in enumerate(handles):
                if not api.GetConsoleMode(handle, ctypes.byref(original)):
                    raise ctypes.WinError(ctypes.get_last_error())
                # Native getwch input + VT output. Disable Quick Edit, line echo,
                # and processed Ctrl-C while choosing, then restore all modes.
                mode = (original.value & ~0x47) | 0x80 if i == 0 else original.value | 0x5
                if not api.SetConsoleMode(handle, mode):
                    raise ctypes.WinError(ctypes.get_last_error())
                changed.append((handle, original.value))
            yield
        finally:
            for handle, mode in reversed(changed):
                api.SetConsoleMode(handle, mode)

    def read_key(self, timeout=.2):
        import msvcrt
        deadline = time.monotonic() + timeout
        while not msvcrt.kbhit():
            if time.monotonic() >= deadline:
                return None
            time.sleep(.01)
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            return {"H": "up", "P": "down", "M": "right", "G": "home", "O": "end"}.get(msvcrt.getwch(), "")
        return {"\r": "enter", "\n": "enter", "\x1b": "back", "\x03": "back", "\x04": "back"}.get(key, key)
