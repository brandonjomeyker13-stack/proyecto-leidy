"""Reglas de negocio del carrito."""

from sqlalchemy.orm import Session

from app.models.cart import CartItem
from app.models.color import Color
from app.repositories import cart_repository, product_color_repository, product_repository
from app.services import product_service
from app.services.product_service import ProductNotFoundError


class InsufficientStockError(Exception):
    pass


class CartItemNotFoundError(Exception):
    pass


class ColorRequiredError(Exception):
    pass


class ColorNotAvailableError(Exception):
    pass


def _validar_color(db, product, color: Color | None) -> None:
    """El color pedido tiene que ser uno de los que ese producto ofrece.

    Si el producto viene en colores, elegir uno es obligatorio: sin eso la
    dueña recibe el pedido sin saber cuál llevar, y la clienta ya lo había
    elegido en la ficha.
    """
    disponibles = [fila.color for fila in product_color_repository.list_by_product(db, product.id)]

    if not disponibles:
        # Producto sin colores: mandar uno sería inventarlo.
        if color is not None:
            raise ColorNotAvailableError(
                f"'{product.name}' no se maneja por colores."
            )
        return

    if color is None:
        raise ColorRequiredError(f"Elige un color para '{product.name}'.")
    if color not in disponibles:
        raise ColorNotAvailableError(
            f"'{product.name}' no viene en {color.value.lower().replace('_', ' ')}."
        )


def add_to_cart(
    db: Session,
    *,
    user_id: int,
    product_id: int,
    quantity: int,
    color: Color | None = None,
) -> CartItem:
    product = product_repository.get_by_id(db, product_id)
    if product is None:
        raise ProductNotFoundError(f"Producto {product_id} no encontrado.")

    _validar_color(db, product, color)

    existing = cart_repository.get_by_user_product_and_color(
        db, user_id, product_id, color
    )
    new_total = (existing.quantity if existing else 0) + quantity

    # La disponibilidad se mira del COLOR, no del total: puede haber 5 en
    # el catálogo y 0 del azul.
    disponible = product_service.stock_disponible(db, product, color)
    if new_total > disponible:
        raise InsufficientStockError(
            f"Solo quedan {disponible} de '{product.name}'"
            + (f" en {color.value.lower().replace('_', ' ')}." if color else ".")
        )

    if existing is not None:
        return cart_repository.update_quantity(db, existing, new_total)

    return cart_repository.create(
        db, user_id=user_id, product_id=product_id, quantity=quantity, color=color
    )


def update_cart_item_quantity(
    db: Session, *, user_id: int, cart_item_id: int, quantity: int
) -> CartItem:
    item = cart_repository.get_by_id(db, cart_item_id)
    if item is None or item.user_id != user_id:
        raise CartItemNotFoundError("Item de carrito no encontrado.")

    product = product_repository.get_by_id(db, item.product_id)
    if product is None:
        raise ProductNotFoundError(f"Producto {item.product_id} no encontrado.")

    disponible = product_service.stock_disponible(db, product, item.color)
    if quantity > disponible:
        raise InsufficientStockError(
            f"Solo quedan {disponible} de '{product.name}'"
            + (f" en {item.color.value.lower().replace('_', ' ')}." if item.color else ".")
        )

    return cart_repository.update_quantity(db, item, quantity)


def get_cart(db: Session, user_id: int) -> list[CartItem]:
    return cart_repository.list_by_user(db, user_id)


def remove_from_cart(db: Session, *, user_id: int, cart_item_id: int) -> None:
    item = cart_repository.get_by_id(db, cart_item_id)
    if item is None or item.user_id != user_id:
        raise CartItemNotFoundError("Item de carrito no encontrado.")
    cart_repository.delete(db, item)