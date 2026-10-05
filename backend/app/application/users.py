"""Compatibility imports for user creation and default categories."""

from app.modules.identity.domain import DEFAULT_CATEGORIES
from app.modules.identity.legacy import create_user

__all__ = ["DEFAULT_CATEGORIES", "create_user"]
