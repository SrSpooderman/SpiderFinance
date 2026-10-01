from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import CategoryIn, CategoryOut, CategoryPatch
from app.application.finance import get_category
from app.infrastructure.models import Category, Transaction

router = APIRouter(prefix="/categories", tags=["categories"])


def validate_category(db: DbSession, user_id: int, name: str, parent_id: int | None, exclude_id: int | None = None) -> None:
    if parent_id is not None:
        parent = get_category(db, user_id, parent_id)
        if parent.parent_id is not None:
            raise HTTPException(422, "Solo se admite un nivel de subcategorías")
        if parent_id == exclude_id:
            raise HTTPException(422, "Una categoría no puede ser su propio padre")
    query = select(Category).where(Category.user_id == user_id, Category.parent_id == parent_id, Category.name == name)
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    sibling = db.scalar(query)
    if sibling:
        raise HTTPException(409, "Ya existe una categoría con ese nombre en este nivel")


@router.get("", response_model=list[CategoryOut])
def list_categories(user: CurrentUser, db: DbSession) -> list[Category]:
    return list(db.scalars(select(Category).where(Category.user_id == user.id).order_by(Category.parent_id, Category.name)))


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, user: CurrentUser, db: DbSession) -> Category:
    validate_category(db, user.id, data.name, data.parent_id)
    category = Category(user_id=user.id, **data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryPatch, user: CurrentUser, db: DbSession) -> Category:
    category = get_category(db, user.id, category_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(422, "El nombre no puede ser nulo")
    name = changes.get("name", category.name)
    parent_id = changes.get("parent_id", category.parent_id)
    if parent_id is not None and db.scalar(select(Category.id).where(Category.parent_id == category_id)):
        raise HTTPException(422, "Una categoría con subcategorías no puede convertirse en subcategoría")
    validate_category(db, user.id, name, parent_id, category_id)
    for key, value in changes.items():
        setattr(category, key, value)
    db.commit()
    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, user: CurrentUser, db: DbSession) -> None:
    category = get_category(db, user.id, category_id)
    if db.scalar(select(Category.id).where(Category.parent_id == category_id).limit(1)) or db.scalar(
        select(Transaction.id).where(Transaction.category_id == category_id).limit(1)
    ):
        raise HTTPException(409, "La categoría está en uso")
    db.delete(category)
    db.commit()
