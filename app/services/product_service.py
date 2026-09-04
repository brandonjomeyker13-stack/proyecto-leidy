"""Reglas de negocio de Product."""

from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.color import Color
from app.models.product import Product
from app.models.product_image import ProductImage
from app.repositories import (
    category_repository,
    product_color_repository,
    product_image_repository,
    product_repository,
)

# Tope de imágenes por producto. Ninguna es obligatoria: un producto
# puede quedarse en 0 y se sigue mostrando (el frontend pone su
# placeholder). El límite existe para que la galería no crezca sin
# control y la ficha siga cargando rápido en celular.
#
# El tope es POR COLOR, no por producto: un bolso que viene en cuatro
# colores necesita fotos de cada uno, y un tope global de 10 le dejaría
# dos fotos por color. Las generales (color en NULL) cuentan como su
# propio grupo.
#
# 10 cubre todos los ángulos útiles de un bolso (frente, atrás, lateral,
# interior, cierre, detalle del material, con la cartuchera, en uso para
# dar escala) con margen de sobra. El costo real de subirlo no es el
# almacenamiento sino los datos móviles de la clienta — pero como solo se
# cargan las fotos del color que ella toque, ese costo no crece con la
# cantidad de colores.
#
# Cambiar este número es lo único que hace falta: el resto del código y
# los tests lo leen de acá.
MAX_PRODUCT_IMAGES = 10


class ProductNotFoundError(Exception):
    pass


class TooManyProductImagesError(Exception):
    pass


class ProductImageNotFoundError(Exception):
    pass


class InsufficientStockError(Exception):
    pass


class ProductHasOrdersError(Exception):
    pass


class CategoryNotFoundError(Exception):
    pass


def create_product(
    db: Session,
    *,
    name: str,
    price: Decimal,
    stock: int,
    category_id: int,
    # Atributos físicos del bolso: opcionales, se completan cuando se
    # tengan (al crear un producto puede que aún no se hayan medido).
    height_cm: Decimal | None = None,
    width_cm: Decimal | None = None,
    compartments: int | None = None,
    material: str | None = None,
    cost: Decimal | None = None,
) -> Product:
    if category_repository.get_by_id(db, category_id) is None:
        raise CategoryNotFoundError(f"Categoría {category_id} no encontrada.")
    return product_repository.create(
        db,
        name=name,
        height_cm=height_cm,
        width_cm=width_cm,
        compartments=compartments,
        material=material,
        price=price,
        stock=stock,
        category_id=category_id,
        cost=cost,
    )


def list_products(
    db: Session, *, skip: int, limit: int, category_id: int | None
) -> list[Product]:
    return product_repository.list_all(
        db, skip=skip, limit=limit, category_id=category_id
    )


def get_product_or_raise(db: Session, product_id: int) -> Product:
    product = product_repository.get_by_id(db, product_id)
    if product is None:
        raise ProductNotFoundError(f"Producto {product_id} no encontrado.")
    return product


def update_product(
    db: Session,
    product_id: int,
    *,
    name: str | None = None,
    price: Decimal | None = None,
    height_cm: Decimal | None = None,
    width_cm: Decimal | None = None,
    compartments: int | None = None,
    material: str | None = None,
    stock: int | None = None,
    category_id: int | None = None,
    cost: Decimal | None = None,
) -> Product:
    product = get_product_or_raise(db, product_id)
    if category_id is not None and category_repository.get_by_id(db, category_id) is None:
        raise CategoryNotFoundError(f"Categoría {category_id} no encontrada.")
    return product_repository.update(
        db,
        product,
        name=name,
        height_cm=height_cm,
        width_cm=width_cm,
        compartments=compartments,
        material=material,
        price=price,
        stock=stock,
        category_id=category_id,
        cost=cost,
    )


def delete_product(db: Session, product_id: int) -> None:
    from app.repositories import cart_repository
    from app.services import order_service

    product = get_product_or_raise(db, product_id)
    cart_repository.delete_by_product(db, product_id)

    # Limpia referencias en pedidos que NO son ventas reales (abandonados,
    # rechazados, expirados). Los pedidos APPROVED se dejan intactos.
    order_service.expire_stale_orders(db)
    order_service.clear_non_approved_references(db, product_id)

    # Se pregunta ANTES de intentar, para poder decir cuáles son los
    # pedidos. El except de abajo queda como red de seguridad por si algo
    # más referencia al producto.
    bloqueantes = order_service.describe_blocking_orders(db, product_id)
    if bloqueantes:
        raise ProductHasOrdersError(
            f"'{product.name}' está en estos pedidos y por eso no se puede "
            f"eliminar: {bloqueantes}. Los pedidos entregados son historial y "
            "no se tocan; los que siguen abiertos se pueden cancelar primero. "
            "Si solo quieres dejar de venderlo, márcalo como agotado "
            "(in_stock = false) en vez de borrarlo."
        )

    try:
        product_repository.delete(db, product)
    except IntegrityError as exc:
        db.rollback()
        raise ProductHasOrdersError(
            f"'{product.name}' está referenciado en otro lado y no se puede "
            "eliminar. Márcalo como agotado (in_stock = false) en su lugar."
        ) from exc


def add_product_images(
    db: Session,
    product_id: int,
    images: list[tuple[str, str | None]],
    color: Color | None = None,
) -> Product:
    """Agrega imágenes al final de la galería de un color. `images` es
    una lista de (url, ruta en el bucket).

    Con `color=None` van al grupo de fotos generales, las que se muestran
    con cualquier variante (el detalle del cierre, la etiqueta). El tope
    se cuenta por grupo, no sobre el total: ver MAX_PRODUCT_IMAGES.

    Se bloquea la fila del producto (`FOR UPDATE`) mientras se cuenta y se
    inserta: sin eso, dos subidas simultáneas leen "hay 3" al mismo
    tiempo y el color termina con más fotos de las que caben.
    """
    product = product_repository.get_by_id_for_update(db, product_id)
    if product is None:
        raise ProductNotFoundError(f"Producto {product_id} no encontrado.")

    actuales = product_image_repository.list_by_color(db, product_id, color)
    disponibles = MAX_PRODUCT_IMAGES - len(actuales)
    if len(images) > disponibles:
        de_que = f"en {color.value.lower()}" if color else "generales"
        raise TooManyProductImagesError(
            f"'{product.name}' ya tiene {len(actuales)} de {MAX_PRODUCT_IMAGES} "
            f"imágenes {de_que}: solo caben {disponibles} más."
        )

    siguiente = len(actuales)
    for offset, (image_url, storage_path) in enumerate(images):
        product_image_repository.add(
            db,
            product_id=product_id,
            image_url=image_url,
            storage_path=storage_path,
            position=siguiente + offset,
            color=color,
        )

    db.refresh(product)
    return product


def set_product_colors(db: Session, product_id: int, colors: list[Color]) -> Product:
    """Deja el producto con exactamente estos colores disponibles.

    Quitar un color NO borra sus fotos: si la dueña deja de ofrecer el
    negro por un tiempo y después vuelve, no tiene que volver a
    fotografiarlo. Las fotos de un color que ya no está disponible
    simplemente no se muestran — el frontend solo pinta círculos de los
    colores que sí están.
    """
    product = get_product_or_raise(db, product_id)
    product_color_repository.set_colors(db, product_id, colors)
    db.refresh(product)
    return product


def delete_product_image(db: Session, product_id: int, image_id: int) -> ProductImage:
    """Quita una imagen de la galería y devuelve la fila borrada, para que
    la capa de API sepa qué archivo eliminar del bucket."""
    image = product_image_repository.get_by_id(db, image_id)
    if image is None or image.product_id != product_id:
        raise ProductImageNotFoundError(
            f"El producto {product_id} no tiene una imagen {image_id}."
        )

    color = image.color
    product_image_repository.delete(db, image)
    # Las que quedan se corren para tapar el hueco: la siguiente pasa a
    # ser la principal y la próxima subida encuentra su lugar libre.
    # Solo dentro de SU color — las galerías de los demás no se tocan.
    product_image_repository.renumber(db, product_id, color)
    return image


def replace_product_images(
    db: Session,
    product_id: int,
    images: list[tuple[str, str | None]],
    color: Color | None = None,
) -> tuple[Product, list[ProductImage]]:
    """Deja la galería de UN color con exactamente estas imágenes.
    Devuelve también las que se quitaron, para borrar sus archivos del
    bucket. Las galerías de los otros colores no se tocan."""
    if len(images) > MAX_PRODUCT_IMAGES:
        raise TooManyProductImagesError(
            f"Un color no puede tener más de {MAX_PRODUCT_IMAGES} imágenes."
        )

    anteriores = product_image_repository.list_by_color(db, product_id, color)
    for image in anteriores:
        product_image_repository.delete(db, image)

    return add_product_images(db, product_id, images, color), anteriores


def reserve_stock(db: Session, product_id: int, quantity: int) -> Product:
    """Descuenta stock al agregar al carrito o confirmar una compra.

    Centralizar esta regla aquí evita que dos rutas distintas de la API
    descuenten stock de forma inconsistente.
    """
    product = get_product_or_raise(db, product_id)
    if product.stock < quantity:
        raise InsufficientStockError(
            f"Stock insuficiente para '{product.name}'. Disponible: {product.stock}."
        )
    return product_repository.update_stock(db, product, product.stock - quantity)