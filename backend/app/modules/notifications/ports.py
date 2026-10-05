"""Outbound mail contract for future application use cases."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MailMessage:
    recipient: str
    subject: str
    text: str
    html: str | None = None


class MailSender(Protocol):
    def send(self, message: MailMessage) -> None: ...
