"""Compatibility exports for shared HTTP dependencies."""

from app.http.dependencies import (
    AdminAuth, CurrentUser, DbSession, bearer, current_user, require_admin,
    require_local_gateway,
)

__all__ = [
    "AdminAuth", "CurrentUser", "DbSession", "bearer", "current_user", "require_admin",
    "require_local_gateway",
]
