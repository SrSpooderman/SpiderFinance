"""Legacy ORM return value for callers of the old user-creation function."""

from sqlalchemy.orm import Session

from app.infrastructure.models import User
from app.modules.identity.infrastructure import CoreCredentials, SqlIdentityStore


def create_user(db: Session, email: str, password: str) -> User:
    user = SqlIdentityStore(db).create_user(email, CoreCredentials().hash(password))
    return db.get(User, user["id"])
