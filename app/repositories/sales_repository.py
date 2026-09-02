"""Acceso a datos para reportes de ventas. Solo SELECT/agregaciones, sin
reglas de negocio.

Qué cuenta como venta: los pedidos con `paid_at` puesto, o sea aquellos
donde la plata YA entró. Antes se filtraba por estado, y con Wompi daba
igual porque se paga antes de entregar. Con contra entrega no: un pedido
puede estar en camino y todavía sin cobrar, y contarlo como ingreso le
mostraría a la dueña plata que no tiene en la mano. `Order.paid_at` lo
pone Wompi al aprobar el pago, o la dueña al confirmar que le pagaron
en la entrega."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem


def _base_query(db: Session):
    return (
        db.query(
            func.sum(OrderItem.unit_price * OrderItem.quantity).label("revenue"),
            func.sum(func.coalesce(OrderItem.unit_cost, 0) * OrderItem.quantity).label("cost"),
            func.sum(OrderItem.quantity).label("items_sold"),
            func.sum(
                case((OrderItem.unit_cost.is_(None), OrderItem.quantity), else_=0)
            ).label("items_without_cost"),
            func.count(func.distinct(Order.id)).label("orders_count"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.paid_at.is_not(None))
    )


def _row_to_summary(row) -> dict:
    # Las sumas vienen como Decimal (las columnas son Numeric(10,2)) y se
    # mantienen así hasta el schema: pasarlas por float redondea, y sobre
    # miles de ítems esa diferencia se acumula en la ganancia reportada.
    revenue: Decimal = row.revenue or Decimal("0")
    cost: Decimal = row.cost or Decimal("0")
    return {
        "revenue": revenue,
        "cost": cost,
        "profit": revenue - cost,
        "items_sold": int(row.items_sold or 0),
        "items_without_cost": int(row.items_without_cost or 0),
        "orders_count": int(row.orders_count or 0),
    }


def get_total_sales(db: Session) -> dict:
    """Ventas de TODO el historial, sin filtro de fecha."""
    row = _base_query(db).one()
    return _row_to_summary(row)


def get_sales_by_period(
    db: Session, granularity: str, *, date_from: datetime, date_to: datetime
) -> list[dict]:
    """granularity: 'day' | 'week' | 'month'. Usa date_trunc de Postgres
    (Supabase corre sobre Postgres, así que esto asume ese motor)."""
    period_col = func.date_trunc(granularity, Order.created_at).label("period")
    rows = (
        db.query(
            period_col,
            func.sum(OrderItem.unit_price * OrderItem.quantity).label("revenue"),
            func.sum(func.coalesce(OrderItem.unit_cost, 0) * OrderItem.quantity).label("cost"),
            func.sum(OrderItem.quantity).label("items_sold"),
            func.sum(
                case((OrderItem.unit_cost.is_(None), OrderItem.quantity), else_=0)
            ).label("items_without_cost"),
            func.count(func.distinct(Order.id)).label("orders_count"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(
            Order.paid_at.is_not(None),
            Order.created_at >= date_from,
            Order.created_at < date_to,
        )
        .group_by(period_col)
        .order_by(period_col)
        .all()
    )
    return [{"period": row.period, **_row_to_summary(row)} for row in rows]