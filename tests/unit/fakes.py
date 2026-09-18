from codex_switch.application.service import SwitchApplication
from codex_switch.domain.models import Account, Preferences, ProxyStatus


class FakeSettings:
    def __init__(self): self.value = Preferences(True)
    def load(self): return self.value
    def save(self, value): self.value = value


class FakeServers:
    def __init__(self): self.items = []
    def list(self): return list(self.items)
    def save(self, server): self.items.append(server)


class FakeAccounts:
    def __init__(self, events):
        self.events = events
        self.items = [Account("one", "Personal", "person@example.com", "plus", True), Account("two", "Work", "work@example.com", "business")]
        self.error = None
    def list(self, **kwargs):
        self.events.append(("list", kwargs))
        return list(self.items)
    def switch(self, key, **kwargs):
        self.events.append(("switch", key, kwargs))
        if self.error: raise self.error
    def login(self, **kwargs): self.events.append(("login", kwargs))


class FakeProxy:
    def __init__(self, events):
        self.events, self.state = events, ProxyStatus()
        self.error = None
    def status(self): return self.state
    def validate(self, server):
        self.events.append(("validate", server.id))
        if self.error: raise self.error
    def start(self, server):
        self.events.append(("start", server.id))
        if self.error: raise self.error
        self.state = ProxyStatus(True, "http://127.0.0.1:10810", server.id)
        return self.state
    def stop(self):
        self.events.append(("stop",))
        self.state = ProxyStatus()
    def check(self): return True


class FakeCodex:
    def __init__(self, events): self.events = events
    def run(self, args, **kwargs):
        self.events.append(("run", args, kwargs))
        return 17


class FakeDiagnostics:
    def dependencies(self): return {"codex": "/fake/codex"}


def application():
    events = []
    app = SwitchApplication(FakeSettings(), FakeServers(), FakeAccounts(events), FakeProxy(events), FakeCodex(events), FakeDiagnostics())
    return app, events
