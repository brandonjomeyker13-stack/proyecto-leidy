"""Order = un pedido ya confirmado (a diferencia del carrito, que es
"lo que estoy pensando comprar"). Se crea al iniciar el checkout, y sus
ítems guardan una FOTO del precio en ese momento — si el producto cambia
de precio después, los pedidos viejos no se ven afectados."""

import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class PaymentMethod(str, enum.Enum):
    """Cómo paga el cliente. Define TODO el flujo del pedido: con WOMPI
    el pago va antes de la entrega; con los otros dos va en el momento
    de la entrega, y por eso necesitan confirmación de las dos partes."""

    WOMPI = "WOMPI"
    CASH = "CASH"  # efectivo, en persona, al recibir
    NEQUI = "NEQUI"  # transferencia por Nequi, al recibir


# Métodos donde la plata se recibe al entregar, no antes.
CONTRA_ENTREGA = {PaymentMethod.CASH, PaymentMethod.NEQUI}


class ClosedBy(str, enum.Enum):
    """Quién cerró el pedido, o sea quién lo llevó a DELIVERED.

    Existe porque sin esto un pedido que la clienta confirmó y uno que la
    tienda cerró sola se ven IDÉNTICOS en la base: los dos quedan en
    DELIVERED con una fecha en `delivery_confirmed_at`. Y no son lo
    mismo: uno es un acuerdo de las dos partes y el otro es una
    declaración de una sola.
    """

    CUSTOMER = "CUSTOMER"  # la clienta confirmó que recibió (y pagó)
    SELLER = "SELLER"  # la tienda lo cerró sin respuesta de la clienta


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"

    # Contra entrega: el pedido quedó cerrado y el stock reservado, pero
    # todavía no se ha pagado. Es un estado aparte de PENDING a propósito:
    # PENDING se cancela solo a las 2 horas (ver PENDING_ORDER_TTL_HOURS,
    # es un carrito abandonado en la pasarela), y un contra entrega vive
    # días hasta que la dueña lo lleve. Si compartieran estado, el barrido
    # de pedidos viejos le cancelaría la compra a la clienta.
    CONFIRMED = "CONFIRMED"

    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    VOIDED = "VOIDED"
    ERROR = "ERROR"
    EXPIRED = "EXPIRED"  # nadie completó el pago a tiempo (abandonado)
    CANCELLED = "CANCELLED"  # el cliente lo canceló él mismo, antes de pagar

    # Logística: solo se llega acá DESPUÉS de APPROVED, nunca directo.
    IN_TRANSIT = "IN_TRANSIT"  # la dueña ya salió a entregar el pedido
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"  # la dueña dice que ya entregó, falta que el cliente confirme
    DELIVERED = "DELIVERED"  # cerrado: lo confirmó la clienta, o lo cerró la dueña


# Los grupos viven acá, junto al enum, y no en un service: los usan tanto
# los services como los repositorios de reportes, y un repositorio no
# puede importar de un service (la dependencia va en el otro sentido).

# Estados en los que un pedido COMPROMETE producto: tiene stock
# reservado y alguien lo está esperando. Se usa para no dejar borrar un
# producto que está en pedidos vivos.
#
# OJO: esto NO es lo mismo que "ya cobré". Antes era un solo conjunto
# porque con Wompi coincidían — se paga antes de entregar, así que un
# pedido comprometido era un pedido pagado. Con contra entrega dejaron de
# coincidir: un pedido puede estar en camino y sin pagar. Para la plata
# está `Order.paid_at`, que es lo que miran los reportes de /sales.
COMMITTED_ORDER_STATUSES = {
    OrderStatus.CONFIRMED,
    OrderStatus.APPROVED,
    OrderStatus.IN_TRANSIT,
    OrderStatus.AWAITING_CONFIRMATION,
    OrderStatus.DELIVERED,
}


# Agrupación para separar "en curso" de "finalizados" en el historial del
# cliente (GET /orders/?stage=active|completed).
ACTIVE_ORDER_STATUSES = {
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.APPROVED,
    OrderStatus.IN_TRANSIT,
    OrderStatus.AWAITING_CONFIRMATION,
}
COMPLETED_ORDER_STATUSES = {
    OrderStatus.DELIVERED,
    OrderStatus.CANCELLED,
    OrderStatus.EXPIRED,
    OrderStatus.DECLINED,
    OrderStatus.VOIDED,
    OrderStatus.ERROR,
}


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Referencia única mandada a Wompi. Es distinta por cada intento de
    # pago (Wompi no permite reusar una referencia), aunque sea del mismo
    # pedido, por eso NO es simplemente el id del pedido.
    reference = Column(String(100), unique=True, nullable=False, index=True)

    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)

    payment_method = Column(
        Enum(PaymentMethod), nullable=False, default=PaymentMethod.WOMPI
    )

    # Cuándo entró la plata DE VERDAD. Con Wompi, cuando aprueba el pago;
    # con contra entrega, cuando la dueña confirma que le pagaron al
    # entregar.
    #
    # Los reportes de /sales filtran por esta columna y no por el estado.
    # Si contaran por estado, un pedido contra entrega en camino —que
    # todavía no cobró nadie— aparecería como ingreso, y la dueña estaría
    # viendo plata que no tiene.
    paid_at = Column(DateTime(timezone=True), nullable=True)

    # Guardado en pesos (no en centavos) para que sea consistente con
    # Product.price. La conversión a centavos para Wompi se hace al vuelo.
    total_amount = Column(Numeric(10, 2), nullable=False)

    # Datos de la transacción de Wompi, una vez que responde (útil para
    # soporte/conciliación sin tener que llamar a su API cada vez).
    wompi_transaction_id = Column(String(100), nullable=True)

    # delivered_at: cuándo la dueña marcó "ya lo entregué" (momento real
    # de la entrega física). Este es el que cuenta para el derecho de
    # retracto de la Ley 1480 (5 días hábiles desde la entrega).
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    # delivery_confirmed_at: cuándo quedó en DELIVERED — porque el
    # cliente confirmó, o porque la dueña lo cerró desde el panel al ver
    # que el cliente nunca volvió a la app.
    #
    # OJO: esta fecha NO distingue quién de los dos lo cerró. Si algún día
    # hace falta saberlo (una discusión sobre una entrega, por ejemplo),
    # eso es una columna nueva, no se puede deducir de acá.
    delivery_confirmed_at = Column(DateTime(timezone=True), nullable=True)

    # Quién lo cerró. En NULL mientras el pedido siga abierto.
    #
    # Un pedido en DELIVERED con esto en NULL es de antes de que existiera
    # la columna: no se sabe quién lo cerró, y no se puede deducir.
    closed_by = Column(Enum(ClosedBy), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    # Foto del producto en el momento de la compra. Si el producto se
    # borra o cambia después, el pedido conserva estos datos igual.
    product_name = Column(String(150), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    unit_cost = Column(Numeric(10, 2), nullable=True)
    quantity = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")