from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.order import OrderStatus, PaymentMethod


class OrderItemRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    unit_price: float
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class OrderCustomerRead(BaseModel):
    """Datos del comprador, para que el panel admin sepa a quién y a
    dónde entregar sin tener que ir a buscarlo aparte."""

    name: str
    email: str
    phone: str | None = None
    address: str | None = None
    city: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderRead(BaseModel):
    id: int
    status: OrderStatus
    payment_method: PaymentMethod
    total_amount: float
    reference: str
    created_at: datetime
    # Cuándo entró la plata. En contra entrega queda en null hasta que la
    # dueña confirme que le pagaron al entregar.
    paid_at: datetime | None = None
    delivered_at: datetime | None = None
    delivery_confirmed_at: datetime | None = None
    items: list[OrderItemRead]
    # Se arma solo desde Order.user (la relación ya existe en el modelo,
    # no hace falta ningún join manual ni endpoint aparte).
    user: OrderCustomerRead

    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdate(BaseModel):
    """Body del PATCH /orders/{id}/status que usa la dueña desde el panel
    admin. Las transiciones válidas se validan en order_service, no acá."""

    status: OrderStatus


class CheckoutRequest(BaseModel):
    """Body del POST /orders/checkout. Si no viene, se asume Wompi para
    no romper a un cliente viejo que todavía no manda el campo."""

    payment_method: PaymentMethod = PaymentMethod.WOMPI


class CheckoutResponse(BaseModel):
    """Lo que el frontend necesita para cerrar el pedido.

    `public_key` y `signature` solo vienen con WOMPI (son del widget). En
    contra entrega llegan en null: no hay pasarela que abrir, el frontend
    muestra las instrucciones de pago y listo.
    """

    order_id: int
    payment_method: PaymentMethod
    currency: str
    amount_in_cents: int
    reference: str
    public_key: str | None = None
    signature: str | None = None