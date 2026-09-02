"""Reglas de negocio de Category."""

from sqlalchemy.orm import Session

from app.models.category import Category
from app.repositories import category_repository


class CategoryAlreadyExistsError(Exception):
    pass


class CategoryNotFoundError(Exception):
    pass


class CategoryHasProductsError(Exception):
    pass


def create_category(db: Session, *, name: str) -> Category:
    name = name.strip()
    if category_repository.get_by_name(db, name) is not None:
        raise CategoryAlreadyExistsError(f"Ya existe una categoría llamada '{name}'.")
    return category_repository.create(db, name=name)


def list_categories(db: Session) -> list[Category]:
    return category_repository.list_all(db)


def get_category_or_raise(db: Session, category_id: int) -> Category:
    category = category_repository.get_by_id(db, category_id)
    if category is None:
        raise CategoryNotFoundError(f"Categoría {category_id} no encontrada.")
    return category


def rename_category(db: Session, category_id: int, *, name: str) -> Category:
    """Cambia el nombre de una categoría.

    Es lo que más se necesita en la práctica: casi nunca quieres borrar
    una categoría, quieres arreglarle un nombre mal escrito. No toca los
    productos — siguen colgando de la misma categoría.
    """
    category = get_category_or_raise(db, category_id)
    name = name.strip()

    otra = category_repository.get_by_name(db, name)
    # Que exista una categoría con ese nombre solo es problema si es OTRA.
    # Renombrar algo a como ya se llamaba no debe fallar: el admin puede
    # estar corrigiendo solo mayúsculas o guardando sin cambios.
    if otra is not None and otra.id != category_id:
        raise CategoryAlreadyExistsError(f"Ya existe una categoría llamada '{name}'.")

    return category_repository.update(db, category, name=name)


def delete_category(db: Session, category_id: int) -> None:
    """Borra una categoría, pero solo si está vacía.

    Todo producto tiene que pertenecer a una categoría
    (Product.category_id es NOT NULL), así que borrar una que tenga
    productos los dejaría huérfanos o rompería la llave foránea. Antes de
    borrar hay que mover esos productos a otra categoría.
    """
    category = get_category_or_raise(db, category_id)

    cuantos = category_repository.count_products(db, category_id)
    if cuantos:
        plural = "productos" if cuantos != 1 else "producto"
        raise CategoryHasProductsError(
            f"'{category.name}' tiene {cuantos} {plural}. Muévelos a otra "
            "categoría antes de eliminarla."
        )

    category_repository.delete(db, category)