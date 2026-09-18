"""The accounts a person can choose, independent of terminal and storage."""
from dataclasses import dataclass

from .models import Account
from .profiles import ProfileStatus


@dataclass(frozen=True)
class AccountEntry:
    id: str
    title: str
    account: Account | None
    profile: ProfileStatus | None = None

    @property
    def original(self) -> bool:
        return self.profile is None

    @property
    def running(self) -> bool:
        return bool(self.profile and self.profile.running)

    @property
    def needs_login(self) -> bool:
        return not self.account or self.account.needs_login

    @property
    def exhausted(self) -> bool:
        return bool(self.account and any(w and w.used_percent >= 100 for w in
                                        (self.account.primary, self.account.secondary)))


def account_catalog(profiles: list[ProfileStatus], originals: list[Account]) -> list[AccountEntry]:
    # Keep original history discoverable, even when an account also has a new home.
    return ([AccountEntry("profile:" + p.name, p.title, p.account, p) for p in profiles]
            + [AccountEntry("original:" + a.key, a.name or a.email, a) for a in originals])
