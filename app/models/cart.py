from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.color import Color


class CartItem(Base):
    """Un producto + cantidad dentro del carrito de un usuario.

    Nota de diseño: si más adelante necesitas un carrito con "estado"
    (abierto, abandonado, convertido en orden), agrega un modelo `Cart`
    con user_id + status, y este `CartItem` pasa a tener cart_id en vez
    de user_id directo. Por ahora, para un e-commerce simple, esto basta.
    """

    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    # Qué color eligió. En NULL si el producto no maneja colores.
    #
    # La misma bolsa en azul y en negro son DOS líneas del carrito, no
    # una con cantidad 2: se agotan por separado y se entregan por
    # separado.
    color = Column(Enum(Color), nullable=True)

    quantity = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="cart_items")
    product = relationship("Product", back_populates="cart_items")