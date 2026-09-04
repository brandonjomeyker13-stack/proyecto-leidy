"""Acceso a datos de los colores de un producto. Sin reglas de negocio."""

from sqlalchemy.orm import Session

from app.models.color import Color
from app.models.product_color import ProductColor


def list_by_product(db: Session, product_id: int) -> list[ProductColor]:
    return (
        db.query(ProductColor)
        .filter(ProductColor.product_id == product_id)
        .order_by(ProductColor.id)
        .all()
    )


def set_colors(db: Session, product_id: int, colors: list[Color]) -> list[ProductColor]:
    """Deja el producto con exactamente estos colores.

    Se conservan las filas de los colores que ya estaban en vez de
    borrarlas y volverlas a crear: si se recrearan, cambiarían de id en
    cada guardado del formulario, y el orden de los círculos en la ficha
    (que sale del id) bailaría sin que nadie tocara nada.
    """
    actuales = {fila.color: fila for fila in list_by_product(db, product_id)}
    pedidos = list(dict.fromkeys(colors))  # sin repetidos, respetando el orden

    for color, fila in actuales.items():
        if color not in pedidos:
            db.delete(fila)

    for color in pedidos:
        if color not in actuales:
            db.add(ProductColor(product_id=product_id, color=color))

    db.commit()
    return list_by_product(db, product_id)
