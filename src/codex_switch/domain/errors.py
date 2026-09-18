class SwitchError(Exception):
    """A message safe to show to a person; never contains credentials."""


class Cancelled(SwitchError):
    pass


class AccountAlreadyAdded(SwitchError):
    def __init__(self, name: str):
        self.name = name
        super().__init__("This account is already saved.")
