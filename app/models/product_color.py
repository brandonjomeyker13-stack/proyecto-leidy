"""En qué colores viene un producto.

Una fila por color disponible. El mismo bolso en gris y en negro es UN
producto con dos filas acá, no dos productos: comparte nombre, precio,
medidas y material, y lo único que cambia es el color y sus fotos.

Va en su propia tabla y no como una lista de colores en una columna
porque así se puede consultar "qué bolsos hay en negro" con un JOIN
normal, y porque la llave foránea impide que quede un color escrito de
una forma que el catálogo no conoce.

OJO CON EL STOCK: las unidades siguen siendo del producto, no del color
(`Product.stock`). O sea que "quedan 3" no dice cuántos de cada color.
Para una tienda donde la dueña coordina cada entrega por WhatsApp antes
de salir, alcanza. Si algún día hace falta stock por color, esta tabla es
el lugar donde iría la columna.
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
