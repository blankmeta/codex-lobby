import os
from pathlib import Path
import subprocess

import psutil

from codex_switch.domain.errors import SwitchError


class NativeProcessControl:
    def _owned(self, pid, config):
        if not isinstance(pid, int) or pid <= 1:
            return None
        try:
            process = psutil.Process(pid)
            args = process.cmdline()
            if not args or Path(args[0]).name.lower() not in ("xray", "xray.exe"):
                return None
            expected = os.path.normcase(str(Path(config).resolve()))
            if not any(arg in ("-c", "-config", "--config") and
                       os.path.normcase(str(Path(args[i + 1]).resolve())) == expected
                       for i, arg in enumerate(args[:-1])):
                return None
            return process if process.is_running() else None
        except (psutil.Error, OSError, ValueError):
            return None

    def identity(self, pid, config):
        process = self._owned(pid, config)
        try:
            return process.create_time() if process else None
        except psutil.Error:
            return None

    def stop(self, pid, config, created_at=None):
        process = self._owned(pid, config)
        if process is None:
            return
        try:
            if created_at is not None and process.create_time() != created_at:
                raise SwitchError("The proxy process changed. Other applications were left running.")
            process.terminate()  # psutil guards against PID reuse before signalling.
            process.wait(timeout=5)
        except psutil.NoSuchProcess:
            pass
        except psutil.Error:
            raise SwitchError("Could not stop the proxy. Retry from Connection settings.") from None


class PosixProcessControl(NativeProcessControl):
    def detached_options(self):
        return {"start_new_session": True}


class WindowsProcessControl(NativeProcessControl):
    def detached_options(self):
        return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
