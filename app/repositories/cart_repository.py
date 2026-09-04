"""Acceso a datos de CartItem. Solo queries, sin reglas de negocio."""

from sqlalchemy.orm import Session

from app.models.cart import CartItem
from app.models.color import Color


def get_by_id(db: Session, cart_item_id: int) -> CartItem | None:
    return db.query(CartItem).filter(CartItem.id == cart_item_id).first()


def get_by_user_product_and_color(
    db: Session, user_id: int, product_id: int, color: Color | None
) -> CartItem | None:
    """La línea del carrito de ese producto EN ESE COLOR.

    El color va en la búsqueda porque el mismo bolso en azul y en negro
    son dos líneas: se agotan por separado y se entregan por separado.
    Buscando solo por producto, agregar el negro habría sumado cantidad a
    la línea del azul.
    """
    condicion = (
        CartItem.color.is_(None) if color is None else CartItem.color == color
    )
    return (
        db.query(CartItem)
        .filter(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
            condicion,
        )
        .first()
    )


def list_by_user(db: Session, user_id: int) -> list[CartItem]:
    return db.query(CartItem).filter(CartItem.user_id == user_id).all()


def create(
    db: Session,
    *,
    user_id: int,
    product_id: int,
    quantity: int,
    color: Color | None = None,
) -> CartItem:
    item = CartItem(
        user_id=user_id, product_id=product_id, quantity=quantity, color=color
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_quantity(db: Session, item: CartItem, quantity: int) -> CartItem:
    item.quantity = quantity
    db.commit()
    db.refresh(item)
    return item


def delete(db: Session, item: CartItem) -> None:
    db.delete(item)
    db.commit()


def delete_for_user_and_products(db: Session, user_id: int, product_ids: list[int]) -> None:
    """Borra, SIN comitear, los ítems de carrito de este usuario que
    coincidan con estos productos. Pensado para usarse dentro de una
    transacción más grande (ej. al confirmar un pago), donde el commit
    final lo hace quien orquesta todo — así no se libera nada a medias."""
    if not product_ids:
        return
    db.query(CartItem).filter(
        CartItem.user_id == user_id, CartItem.product_id.in_(product_ids)
    ).delete(synchronize_session=False)


def delete_by_product(db: Session, product_id: int) -> None:
    """Borra todos los ítems de carrito (de cualquier usuario) que referencien
    a este producto. Se usa antes de eliminar un producto, ya que si el
    producto deja de existir no tiene sentido que siga en algún carrito."""
    db.query(CartItem).filter(CartItem.product_id == product_id).delete()
    db.commit()