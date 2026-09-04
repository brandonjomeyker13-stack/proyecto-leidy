"""Imágenes de un producto: varias, todas opcionales.

Van en su propia tabla y no en columnas fijas (`image_url_1`,
`image_url_2`, ...) porque así hay que tocar la base cada vez que cambie
el máximo, y borrar la segunda de tres imágenes obliga a ir corriendo las
demás a mano. Acá una fila es una imagen: no hay huecos que rellenar y el
tope es una regla de negocio (product_service.MAX_PRODUCT_IMAGES), no una
restricción del esquema — subirlo de 4 a 8 no necesitó migración.
"""

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.color import Color


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        Integer,
        # Si se borra el producto, se van sus imágenes: solas no
        # significan nada.
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # URL pública del archivo en Supabase Storage (bucket "product-images").
    # El archivo en sí NO vive en esta base de datos, solo el link.
    image_url = Column(String(500), nullable=False)

    # Ruta del archivo dentro del bucket. Se guarda aparte de la URL
    # pública porque es lo que hay que mandarle a Supabase para borrarlo:
    # sin esto, cada imagen reemplazada quedaría ocupando espacio para
    # siempre.
    storage_path = Column(String(500), nullable=True)

    # De qué color es esta foto. En NULL cuando la foto sirve para
    # cualquier color (el detalle del cierre, la etiqueta, una toma del
    # interior): esas se muestran siempre, sin importar qué círculo toque
    # la clienta.
    #
    # No hay llave foránea a product_colors a propósito: si la dueña deja
    # de ofrecer el negro, las fotos del negro no se borran solas — las
    # quita ella cuando quiera. Una FK con cascada le habría borrado
    # trabajo sin avisar.
    color = Column(Enum(Color), nullable=True, index=True)

    # Orden dentro de la galería de SU color. La 0 es la principal.
    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="images")

    __table_args__ = (
        # Dos imágenes no pueden pelear por el mismo lugar DENTRO de su
        # color. El color entra en la llave porque cada color tiene su
        # propia galería numerada desde 0: sin él, la primera foto del
        # negro chocaría con la primera del gris.
        UniqueConstraint(
            "product_id",
            "color",
            "position",
            name="uq_product_images_product_color_position",
        ),
    )
