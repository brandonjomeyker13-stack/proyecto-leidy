""" endpoints del producto"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.core.storage import delete_product_image_file, upload_product_image
from app.db.session import get_db
from app.models.color import Color, listar_catalogo
from app.models.product_image import ProductImage
from app.models.user import User
from app.schemas.product import (
    ColorStockUpdate,
    ProductAdminRead,
    ProductColorsUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.services import product_service

router = APIRouter()


@router.get("/", response_model=list[ProductRead])
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(
        product_service.MAX_PRODUCTS_LISTED,
        ge=1,
        le=product_service.MAX_PRODUCTS_LISTED,
    ),
    category_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return product_service.list_products(
        db, skip=skip, limit=limit, category_id=category_id
    )


@router.get("/colors")
def list_colors():
    """El catálogo de colores de la tienda, con nombre y hex.

    Se declara ANTES de /{product_id} a propósito: si fuera después,
    FastAPI intentaría leer "colors" como un id de producto y devolvería
    un 422 en vez de este listado.

    El frontend lo consume para pintar los círculos, en vez de copiar la
    paleta a mano y arriesgarse a que se separen.
    """
    return listar_catalogo()


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    try:
        return product_service.get_product_or_raise(db, product_id)
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{product_id}/admin", response_model=ProductAdminRead)
def get_product_admin(
    product_id: int,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    """Igual que GET /{product_id}, pero solo-admin e incluye `cost` —
    para poder precargar el campo Costo en el formulario de edición."""
    try:
        return product_service.get_product_or_raise(db, product_id)
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/", response_model=ProductAdminRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    try:
        producto = product_service.create_product(
            db,
            name=payload.name,
            height_cm=payload.height_cm,
            width_cm=payload.width_cm,
            compartments=payload.compartments,
            material=payload.material,
            price=payload.price,
            stock=payload.stock,
            category_id=payload.category_id,
            cost=payload.cost,
        )
        if payload.colors:
            producto = product_service.set_product_colors(db, producto.id, payload.colors)
        return producto
    except product_service.CategoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{product_id}", response_model=ProductAdminRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    try:
        producto = product_service.update_product(
            db,
            product_id,
            name=payload.name,
            height_cm=payload.height_cm,
            width_cm=payload.width_cm,
            compartments=payload.compartments,
            material=payload.material,
            price=payload.price,
            stock=payload.stock,
            category_id=payload.category_id,
            cost=payload.cost,
        )
        # Los colores viven en su propia tabla, así que se actualizan
        # aparte. `None` significa "no los toques"; una lista vacía sí es
        # una orden: dejar el producto sin colores.
        if payload.colors is not None:
            producto = product_service.set_product_colors(db, product_id, payload.colors)
        return producto
    except product_service.StockManagedByColorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except product_service.ColorStillHasStockError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except product_service.CategoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{product_id}/colors", response_model=ProductAdminRead)
def set_product_colors(
    product_id: int,
    payload: ProductColorsUpdate,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    """Deja el producto con exactamente estos colores disponibles.

    Reemplaza la lista completa, no agrega: lo que no venga en el body se
    quita. Es lo que espera un formulario de círculos donde el admin
    marca y desmarca — mandar el estado final es más simple y menos
    propenso a errores que mandar altas y bajas por separado.

    Quitar un color NO borra sus fotos.
    """
    try:
        return product_service.set_product_colors(db, product_id, payload.colors)
    except product_service.ColorStillHasStockError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{product_id}/colors/{color}/stock", response_model=ProductAdminRead)
def set_color_stock(
    product_id: int,
    color: Color,
    payload: ColorStockUpdate,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    """Cuántas unidades hay de un color.

    El stock vive en cada color, no en el producto: el azul y el negro se
    agotan por separado. `products.stock` queda como la suma y lo
    recalcula el backend — no hace falta (ni se debe) mandarlo aparte.
    """
    try:
        return product_service.set_color_stock(db, product_id, color, payload.stock)
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except product_service.ColorNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    try:
        product_service.delete_product(db, product_id)
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except product_service.ProductHasOrdersError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _borrar_del_bucket(imagenes: list[ProductImage]) -> None:
    for image in imagenes:
        if image.storage_path:
            delete_product_image_file(image.storage_path)


@router.post("/{product_id}/images", response_model=ProductAdminRead)
async def upload_images(
    product_id: int,
    files: list[UploadFile],
    color: Color | None = None,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    """Agrega imágenes a la galería de un color del producto.

    `color` va como query param. Sin él, las fotos quedan como generales:
    se muestran sin importar qué círculo toque la clienta (el detalle del
    cierre, la etiqueta, el interior).

    El tope es por color, no sobre el total del producto — un bolso en
    cuatro colores necesita fotos de cada uno.

    Ninguna es obligatoria: un producto puede quedarse sin imágenes. Se
    pueden mandar varias en el mismo request (campo `files` repetido).
    """
    try:
        product_service.get_product_or_raise(db, product_id)
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if len(files) > product_service.MAX_PRODUCT_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Máximo {product_service.MAX_PRODUCT_IMAGES} imágenes por color.",
        )

    subidas = [await upload_product_image(file, product_id) for file in files]

    try:
        return product_service.add_product_images(
            db, product_id, [(subida.url, subida.path) for subida in subidas], color
        )
    except product_service.TooManyProductImagesError as exc:
        # Ya estaban en el bucket cuando se supo que no cabían: se limpian
        # para no dejar archivos que nadie referencia.
        for subida in subidas:
            delete_product_image_file(subida.path)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{product_id}/images/{image_id}", response_model=ProductAdminRead)
def delete_image(
    product_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    """Quita una imagen. Las que quedan se corren un lugar, así que la
    siguiente pasa a ser la principal."""
    try:
        borrada = product_service.delete_product_image(db, product_id, image_id)
    except product_service.ProductImageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    _borrar_del_bucket([borrada])
    return product_service.get_product_or_raise(db, product_id)


@router.post("/{product_id}/image", response_model=ProductAdminRead, deprecated=True)
async def upload_image(
    product_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    is_admin: User = Depends(get_current_admin_user),
):
    """Deja el producto con esta única imagen (reemplaza las que tuviera).

    Es el endpoint viejo de una sola imagen, se mantiene para no romper al
    frontend que ya lo llama. Para la galería usa POST /{id}/images.
    """
    try:
        product_service.get_product_or_raise(db, product_id)
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    subida = await upload_product_image(file, product_id)
    product, anteriores = product_service.replace_product_images(
        db, product_id, [(subida.url, subida.path)]
    )
    _borrar_del_bucket(anteriores)
    return product