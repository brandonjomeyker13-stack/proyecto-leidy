from datetime import datetime

from pydantic import BaseModel


class SalesSummary(BaseModel):
    """Ingresos/costo/ganancia calculados SOLO sobre pedidos que ya se
    cobraron de verdad, o sea los que tienen `Order.paid_at` puesto.

    No es lo mismo que "pedidos entregados": un contra entrega en camino
    todavía no cobró nada, y contarlo acá mostraría plata que no está.

    items_without_cost > 0 significa que algunos productos vendidos no
    tenían `cost` cargado en ese momento — la ganancia mostrada está
    subestimando el costo real (asume 0 para esos ítems)."""

    revenue: float
    cost: float
    profit: float
    items_sold: int
    items_without_cost: int
    orders_count: int


class SalesPeriod(SalesSummary):
    period: datetime