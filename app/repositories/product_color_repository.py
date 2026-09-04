"""Acceso a datos de los colores de un producto. Sin reglas de negocio.

Acá vive también el stock por color, y con él la ÚNICA regla de
consistencia que importa: cada vez que se mueve el stock de un color se
recalcula `products.stock` como la suma. Ese total no se edita en ningún
otro lado — si se editara, los dos números se irían separando y nadie
sabría cuál creer.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.color import Color
from app.models.product import Product
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


def get(db: Session, product_id: int, color: Color) -> ProductColor | None:
    return (
        db.query(ProductColor)
        .filter(ProductColor.product_id == product_id, ProductColor.color == color)
        .first()
    )


def get_for_update(db: Session, product_id: int, color: Color) -> ProductColor | None:
    """El color de un producto con su fila bloqueada (SELECT ... FOR UPDATE).

    Igual que product_repository.get_by_id_for_update: úsalo dentro de un
    flujo donde quien llama controla el commit final. Si haces commit a
    mitad, sueltas el lock y dos compras simultáneas pueden leer el mismo
    stock viejo y vender la misma unidad dos veces.
    """
    return (
        db.query(ProductColor)
        .filter(ProductColor.product_id == product_id, ProductColor.color == color)
        .with_for_update()
        .first()
    )


def recompute_product_stock(db: Session, product_id: int) -> None:
    """Deja `products.stock` igual a la suma de sus colores, SIN commitear.

    Es lo que mantiene coherente el total con el detalle. Un producto sin
    colores no se toca: ahí el stock vive directo en el producto.
    """
    filas = (
        db.query(func.count(ProductColor.id), func.coalesce(func.sum(ProductColor.stock), 0))
        .filter(ProductColor.product_id == product_id)
        .one()
    )
    cuantos_colores, total = filas
    if not cuantos_colores:
        return

    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        return
    product.stock = int(total)
    product.in_stock = product.stock > 0


def apply_stock_delta(db: Session, fila: ProductColor, delta: int) -> ProductColor:
    """Suma `delta` al stock de un color (negativo para descontar), SIN
    commitear, y recalcula el total del producto."""
    fila.stock = max(0, fila.stock + delta)
    db.flush()
    recompute_product_stock(db, fila.product_id)
    return fila


def set_stock(db: Session, product_id: int, color: Color, stock: int) -> ProductColor:
    """Fija el stock de un color desde el panel. Este sí commitea."""
    fila = get_for_update(db, product_id, color)
    if fila is None:
        raise ValueError(f"El producto {product_id} no viene en {color.value}.")
    fila.stock = max(0, stock)
    db.flush()
    recompute_product_stock(db, product_id)
    db.commit()
    db.refresh(fila)
    return fila
