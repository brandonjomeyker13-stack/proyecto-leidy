"""En qué colores viene un producto.

Una fila por color disponible. El mismo bolso en gris y en negro es UN
producto con dos filas acá, no dos productos: comparte nombre, precio,
medidas y material, y lo único que cambia es el color y sus fotos.

Va en su propia tabla y no como una lista de colores en una columna
porque así se puede consultar "qué bolsos hay en negro" con un JOIN
normal, y porque la llave foránea impide que quede un color escrito de
una forma que el catálogo no conoce.

EL STOCK VIVE ACÁ. Cada color tiene sus propias unidades, porque el
azul y el negro se agotan por separado. `Product.stock` se conserva como
la SUMA de los colores —para el catálogo, `in_stock` y los reportes— y lo
recalcula solo `product_color_repository`: no es un segundo lugar donde
editarlo.

Lo que sí se hereda del producto: nombre, precio, costo, categoría,
medidas y material. Un color no es un producto aparte, es la misma bolsa
en otro tono.
"""

from sqlalchemy import Column, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.color import CATALOGO, Color


class ProductColor(Base):
    __tablename__ = "product_colors"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        Integer,
        # Si se borra el producto, se van sus colores: solos no
        # significan nada.
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    color = Column(Enum(Color), nullable=False)

    # Unidades disponibles DE ESTE COLOR. El total del producto es la suma
    # de estas, y lo mantiene product_color_repository.
    stock = Column(Integer, nullable=False, default=0, server_default="0")

    product = relationship("Product", back_populates="colors")

    # El nombre y el hex salen del catálogo, no de la base: si se
    # guardaran acá, cambiar una tonalidad obligaría a un UPDATE masivo y
    # los productos viejos se quedarían con el tono anterior.
    @property
    def value(self) -> Color:
        return self.color

    @property
    def label(self) -> str:
        return CATALOGO[self.color][0]

    @property
    def hex(self) -> str:
        return CATALOGO[self.color][1]

    __table_args__ = (
        # El mismo color dos veces en el mismo producto sería un círculo
        # repetido en la ficha.
        UniqueConstraint("product_id", "color", name="uq_product_colors_product_color"),
    )
