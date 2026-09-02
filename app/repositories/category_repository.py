"""Acceso a datos de Category. Solo queries, sin reglas de negocio."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product


def get_by_id(db: Session, category_id: int) -> Category | None:
    return db.query(Category).filter(Category.id == category_id).first()


def get_by_name(db: Session, name: str) -> Category | None:
    return db.query(Category).filter(Category.name == name).first()


def list_all(db: Session) -> list[Category]:
    return db.query(Category).order_by(Category.name).all()


def create(db: Session, *, name: str) -> Category:
    category = Category(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update(db: Session, category: Category, *, name: str) -> Category:
    category.name = name
    db.commit()
    db.refresh(category)
    return category


def delete(db: Session, category: Category) -> None:
    db.delete(category)
    db.commit()


def count_products(db: Session, category_id: int) -> int:
    """Cuántos productos cuelgan de esta categoría.

    Con un COUNT y no con len(category.products): esto se usa solo para
    decidir si se puede borrar, y traer todos los productos a memoria
    para contarlos sería trabajo tirado a la basura."""
    return (
        db.query(func.count(Product.id))
        .filter(Product.category_id == category_id)
        .scalar()
    )