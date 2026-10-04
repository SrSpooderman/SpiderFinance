from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.infrastructure.models import Category, User, UserSettings

DEFAULT_CATEGORIES = (
    "Alimentación", "Restaurantes", "Transporte", "Ocio", "Ropa", "Tecnología",
    "Estudios", "Salud", "Viajes", "Hogar", "Suscripciones", "Deporte",
    "Regalos", "Mascotas", "Impuestos", "Comisiones", "Otros",
)


def create_user(db: Session, email: str, password: str) -> User:
    user = User(email=email.lower(), password_hash=hash_password(password))
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    db.add_all(Category(user_id=user.id, name=name) for name in DEFAULT_CATEGORIES)
    db.commit()
    db.refresh(user)
    return user
