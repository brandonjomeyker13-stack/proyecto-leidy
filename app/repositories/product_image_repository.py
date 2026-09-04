"""Acceso a datos de las imágenes de un producto. Sin reglas de negocio:
el tope y el orden de la galería los decide product_service.

Cada color tiene su propia galería numerada desde 0, así que casi todo
acá recibe un `color`. Ojo: `color=None` NO significa "todos los
colores" — significa las fotos GENERALES, las que se muestran con
cualquier variante. Para traer todas existe `list_by_product`.
"""

from sqlalchemy.orm import Session

from app.models.color import Color
from app.models.product_image import ProductImage


def list_by_product(db: Session, product_id: int) -> list[ProductImage]:
    """TODAS las fotos del producto, de todos los colores."""
    return (
        db.query(ProductImage)
        .filter(ProductImage.product_id == product_id)
        .order_by(ProductImage.color, ProductImage.position)
        .all()
    )


def list_by_color(
    db: Session, product_id: int, color: Color | None
) -> list[ProductImage]:
    """Las fotos de UN color. Con `color=None`, las generales."""
    condicion = (
        ProductImage.color.is_(None) if color is None else ProductImage.color == color
    )
    return (
        db.query(ProductImage)
        .filter(ProductImage.product_id == product_id, condicion)
        .order_by(ProductImage.position)
        .all()
    )


def get_by_id(db: Session, image_id: int) -> ProductImage | None:
    return db.query(ProductImage).filter(ProductImage.id == image_id).first()


def add(
    db: Session,
    *,
    product_id: int,
    image_url: str,
    storage_path: str | None,
    position: int,
    color: Color | None = None,
) -> ProductImage:
    image = ProductImage(
        product_id=product_id,
        image_url=image_url,
        storage_path=storage_path,
        position=position,
        color=color,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


def delete(db: Session, image: ProductImage) -> None:
    db.delete(image)
    db.commit()


def renumber(db: Session, product_id: int, color: Color | None = None) -> None:
    """Deja en 0, 1, 2... las posiciones de UN color, sin huecos.

    Hace falta después de borrar: si quedaban las posiciones 0 y 2 y se
    sube una imagen nueva, sin renumerar se calcularía la posición 2 otra
    vez y chocaría con la constraint (product_id, color, position).

    Renumera solo dentro del color, no toda la galería: las fotos del
    negro y las del gris tienen numeraciones independientes, y correr las
    de un color por haber borrado en otro sería reordenar sin motivo.
    """
    imagenes = list_by_color(db, product_id, color)

    # El desplazamiento a negativos es para no chocar contra la constraint
    # en el camino: pasar la posición 2 a la 1 mientras la 1 todavía
    # existe rompería la unicidad a mitad del renumerado.
    for offset, image in enumerate(imagenes):
        image.position = -(offset + 1)
    db.flush()

    for offset, image in enumerate(imagenes):
        image.position = offset
    db.commit()
