from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.color import Color
from app.schemas.category import CategoryRead


class ColorStockUpdate(BaseModel):
    """Body de PUT /products/{id}/colors/{color}/stock."""

    stock: int = Field(..., ge=0)


class ProductColorRead(BaseModel):
    """Un color disponible, listo para que el frontend pinte el círculo.

    Trae el nombre y el hex resueltos para que el frontend no tenga que
    cruzarlos contra el catálogo por su cuenta ni copiarlos a mano.
    """

    value: Color
    label: str
    hex: str
    # Unidades de ESE color. El `stock` del producto es la suma de todos.
    stock: int

    model_config = ConfigDict(from_attributes=True)


class ProductImageRead(BaseModel):
    id: int
    image_url: str
    position: int
    # De qué color es esta foto. En null si es general: esas se muestran
    # sin importar qué círculo toque la clienta.
    color: Color | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    height_cm: Decimal | None = Field(default=None, gt=0, decimal_places=1)
    width_cm: Decimal | None = Field(default=None, gt=0, decimal_places=1)
    compartments: int | None = Field(default=None, ge=0)
    material: str | None = Field(default=None, min_length=2, max_length=100)
    price: Decimal = Field(..., gt=0, decimal_places=2)
    stock: int = Field(default=0, ge=0)
    in_stock: bool = True


class ProductCreate(ProductBase):
    # Obligatoria: no tiene default, el admin SIEMPRE debe indicar a qué
    # categoría (ya existente) pertenece el producto.
    category_id: int = Field(...)

    # Opcional a propósito (puede que no lo sepas al crear el producto).
    # Costo de compra/fabricación, para calcular ganancia en /sales.
    cost: Decimal | None = Field(default=None, ge=0, decimal_places=2)

    # En qué colores viene. Vacío es válido: se pueden marcar después,
    # desde PUT /products/{id}/colors.
    colors: list[Color] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """Todos los campos opcionales: solo se actualiza lo que se envíe."""

    name: str | None = Field(default=None, min_length=2, max_length=150)
    height_cm: Decimal | None = Field(default=None, gt=0, decimal_places=1)
    width_cm: Decimal | None = Field(default=None, gt=0, decimal_places=1)
    compartments: int | None = Field(default=None, ge=0)
    material: str | None = Field(default=None, min_length=2, max_length=100)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)
    category_id: int | None = Field(default=None)
    cost: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    # None = no tocar los colores. Lista vacía = dejarlo sin colores.
    colors: list[Color] | None = Field(default=None)


class ProductColorsUpdate(BaseModel):
    """Body de PUT /products/{id}/colors: la lista COMPLETA de colores
    disponibles. Vacía es válida — deja el producto sin colores."""

    colors: list[Color] = Field(default_factory=list)


class ProductRead(ProductBase):
    """Vista PÚBLICA — la usan los endpoints que cualquiera puede llamar
    (GET /products/, GET /products/{id}). A propósito NO incluye `cost`:
    eso revelaría el margen de ganancia a cualquier cliente."""

    id: int
    category: CategoryRead

    # Los colores disponibles, cada uno con su nombre y su hex.
    colors: list[ProductColorRead] = []

    # De 0 a 4, en el orden en que se muestran. La primera es la
    # principal.
    images: list[ProductImageRead] = []

    # La URL de la imagen principal, o None si no tiene ninguna. Sale de
    # `images[0]`; se mantiene en la respuesta para no romper al frontend
    # que ya la usa.
    image_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductAdminRead(ProductRead):
    """Vista SOLO-ADMIN — la usan los endpoints protegidos con
    get_current_admin_user (crear/editar/subir imagen). Incluye `cost`
    para que el admin pueda ver y editar el costo cargado."""

    cost: Decimal | None = None