class SwitchError(Exception):
    """A message safe to show to a person; never contains credentials."""


class Cancelled(SwitchError):
    pass


class MissingTool(SwitchError):
    def __init__(self, name):
        self.name = name
        super().__init__(f"{name} is not installed. Open Settings → Install tools, then try again.")


class AccountAlreadyAdded(SwitchError):
    def __init__(self, name: str):
        self.name = name
        super().__init__("This account is already saved.")
