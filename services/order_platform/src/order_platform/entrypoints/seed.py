"""Seed the Order Platform database (LLD-7 L7f).

Golden fixtures (C0001-C0010, ORD-100001 onwards) back the evaluation scenarios; Faker
(en_IN, fixed seed) adds realistic filler. All dates are relative to an anchor date.

  order-platform-seed --reset
"""

import argparse
import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from faker import Faker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from order_platform.adapters.db import migrate
from order_platform.adapters.db.tables import (
    CustomerRow,
    OrderItemRow,
    OrderRow,
    ProductRow,
    ShipmentEventRow,
    ShipmentRow,
)
from order_platform.entrypoints.composition import Database
from order_platform.entrypoints.settings import Settings

SEED = 42
FREE_SHIPPING_FROM_PAISE = 49_900
SHIPPING_FEE_PAISE = 4_900

# sku, name, category, accessory, price (₹), warranty months
CATALOG = [
    ("ELE-HEADPHONES", "Wireless Headphones", "electronics", False, 2999, 12),
    ("ELE-SPEAKER", "Bluetooth Speaker", "electronics", False, 3499, 12),
    ("ELE-SMARTWATCH", "Smartwatch", "electronics", False, 12999, 12),
    ("ELE-LAPTOP14", "Laptop 14-inch", "electronics", False, 54990, 12),
    ("ELE-PHONE", "Smartphone", "electronics", False, 24999, 12),
    ("ELE-POWERBANK", "Power Bank 20000mAh", "electronics", True, 1799, 6),
    ("ELE-CHARGER", "Fast Charger 33W", "electronics", True, 899, 6),
    ("ELE-MIXER", "Mixer Grinder", "electronics", False, 3999, 24),
    ("APP-KURTA", "Cotton Kurta", "apparel", False, 1499, 0),
    ("APP-SHOES", "Running Shoes", "apparel", False, 4200, 0),
    ("APP-JEANS", "Denim Jeans", "apparel", False, 1999, 0),
    ("APP-JACKET", "Winter Jacket", "apparel", False, 2799, 0),
    ("GRO-RICE5", "Basmati Rice 5kg", "groceries", False, 850, 0),
    ("GRO-OIL1", "Cold-pressed Oil 1L", "groceries", False, 420, 0),
    ("GRO-DRYFRUIT", "Dry Fruits Combo", "groceries", False, 1250, 0),
    ("HOM-COOKER5", "Pressure Cooker 5L", "home_kitchen", False, 3499, 24),
    ("HOM-COOKWARE", "Non-stick Cookware Set", "home_kitchen", False, 2899, 12),
    ("HOM-BEDSHEET", "Bedsheet Set", "home_kitchen", False, 1299, 0),
    ("BEA-SERUM", "Vitamin C Serum", "beauty", False, 1200, 0),
    ("BEA-DRYER", "Hair Dryer", "beauty", False, 1899, 12),
    ("BEA-SUNSCREEN", "Sunscreen SPF 50", "beauty", False, 549, 0),
]
CARRIERS = ["Delhivery", "Blue Dart", "Ekart", "Xpressbees", "Shadowfax", "India Post"]
HUBS = ["Bhiwandi Hub", "Gurugram Hub", "Hoskote Hub", "Shamshabad Hub", "Kolkata Hub"]

# customer_no, name, city, tier, abuse_flag
FIXTURE_CUSTOMERS = [
    ("C0001", "Priya Sharma", "Bengaluru", "gold", False),
    ("C0002", "Rahul Verma", "Delhi", "regular", False),
    ("C0003", "Ananya Iyer", "Chennai", "regular", False),
    ("C0004", "Vikram Singh", "Jaipur", "regular", True),
    ("C0005", "Meera Nair", "Kochi", "platinum", False),
    ("C0006", "Arjun Reddy", "Hyderabad", "regular", False),
    ("C0007", "Sneha Gupta", "Pune", "gold", False),
    ("C0008", "Karan Mehta", "Mumbai", "regular", False),
    ("C0009", "Fatima Khan", "Lucknow", "regular", False),
    ("C0010", "Rohan Das", "Kolkata", "regular", False),
]


@dataclass(frozen=True, slots=True)
class OrderSpec:
    order_no: str
    customer_no: str
    skus: tuple[str, ...]
    placed_days_ago: int
    order_status: str
    shipment_status: str | None
    promised_days_ago: int
    delivered_days_ago: int | None
    payment: str = "UPI"


# One order per evaluation scenario (LLD-7)
FIXTURE_ORDERS = [
    OrderSpec("ORD-100001", "C0001", ("ELE-HEADPHONES",), 24, "delivered", "delivered", 21, 20),
    OrderSpec(
        "ORD-100002", "C0001", ("APP-KURTA",), 13, "delivered", "delivered", 10, 10, "Credit Card"
    ),
    OrderSpec(
        "ORD-100003", "C0002", ("ELE-LAPTOP14",), 8, "delivered", "delivered", 6, 5, "Credit Card"
    ),
    OrderSpec("ORD-100004", "C0003", ("GRO-RICE5",), 3, "delivered", "delivered", 1, 1),
    OrderSpec(
        "ORD-100005", "C0004", ("ELE-SMARTWATCH",), 11, "delivered", "delivered", 8, 8, "COD"
    ),
    OrderSpec("ORD-100006", "C0005", ("ELE-SPEAKER",), 12, "shipped", "in_transit", 5, None),
    OrderSpec(
        "ORD-100007", "C0006", ("HOM-COOKER5",), 30, "delivered", "delivered", 26, 26, "Debit Card"
    ),
    OrderSpec("ORD-100008", "C0007", ("APP-SHOES",), 43, "delivered", "delivered", 40, 40),
    OrderSpec(
        "ORD-100009", "C0008", ("ELE-PHONE",), 25, "delivered", "delivered", 21, 21, "Credit Card"
    ),
    OrderSpec("ORD-100010", "C0009", ("BEA-SERUM",), 9, "delivered", "delivered", 5, 4),
    OrderSpec(
        "ORD-100011", "C0010", ("ELE-POWERBANK",), 18, "shipped", "lost", 9, None, "Net Banking"
    ),
    OrderSpec("ORD-100012", "C0002", ("ELE-MIXER",), 6, "delivered", "delivered", 3, 3),
    OrderSpec("ORD-100013", "C0001", ("GRO-OIL1",), 5, "delivered", "delivered", 2, 2),
    OrderSpec("ORD-100014", "C0003", ("APP-JEANS", "APP-JACKET"), 2, "placed", None, -3, None),
]


async def seed(engine: AsyncEngine, anchor: date, *, reset: bool) -> dict[str, int]:
    if reset:
        await migrate.reset(engine)
        await migrate.upgrade(engine)
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sessions() as session:
        builder = _Builder(session, anchor)
        await builder.build()
        await session.commit()
        return await _counts(session)


class _Builder:
    def __init__(self, session: AsyncSession, anchor: date) -> None:
        self.s, self.anchor = session, anchor
        self.rng = random.Random(SEED)  # noqa: S311 - reproducible test data
        self.fake = Faker("en_IN")
        Faker.seed(SEED)
        self.customers: dict[str, CustomerRow] = {}
        self.products: dict[str, ProductRow] = {}

    async def build(self) -> None:
        self._products()
        for cno, name, city, tier, abuse in FIXTURE_CUSTOMERS:
            self._customer(cno, name, city, tier, abuse)
        for spec in FIXTURE_ORDERS:
            self._order(spec)
        self._filler(customers=50, orders=300)

    def _at(self, days_ago: int, hour: int = 11) -> datetime:
        return datetime.combine(self.anchor - timedelta(days=days_ago), time(hour), UTC)

    def _products(self) -> None:
        for sku, name, cat, acc, rupees, warranty in CATALOG:
            row = ProductRow(
                sku=sku,
                name=name,
                category=cat,
                is_accessory=acc,
                price_paise=rupees * 100,
                warranty_months=warranty,
            )
            self.products[sku] = row
            self.s.add(row)

    def _customer(self, cno: str, name: str, city: str, tier: str, abuse: bool) -> None:
        email = name.lower().replace(" ", ".") + "@example.in"
        row = CustomerRow(
            customer_no=cno,
            name=name,
            email=email,
            phone=self.fake.phone_number(),
            city=city,
            tier=tier,
            abuse_flag=abuse,
            created_at=self._at(400),
        )
        self.customers[cno] = row
        self.s.add(row)

    def _order(self, spec: OrderSpec) -> None:
        items = [self.products[sku] for sku in spec.skus]
        subtotal = sum(p.price_paise for p in items)
        order = OrderRow(
            order_no=spec.order_no,
            customer=self.customers[spec.customer_no],
            status=spec.order_status,
            payment_method=spec.payment,
            placed_at=self._at(spec.placed_days_ago),
            shipping_fee_paise=0 if subtotal >= FREE_SHIPPING_FROM_PAISE else SHIPPING_FEE_PAISE,
        )
        order.items = [
            OrderItemRow(product=p, qty=1, unit_price_paise=p.price_paise, refunded_paise=0)
            for p in items
        ]
        if spec.shipment_status:
            order.shipment = self._shipment(spec)
        self.s.add(order)

    def _shipment(self, spec: OrderSpec) -> ShipmentRow:
        carrier = self.rng.choice(CARRIERS)
        delivered = (
            self._at(spec.delivered_days_ago, 15) if spec.delivered_days_ago is not None else None
        )
        shipment = ShipmentRow(
            carrier=carrier,
            awb=f"{carrier[:2].upper()}{self.rng.randint(10**9, 10**10 - 1)}",
            status=spec.shipment_status,
            promised_date=self.anchor - timedelta(days=spec.promised_days_ago),
            delivered_at=delivered,
        )
        shipment.events = self._events(spec)
        return shipment

    def _events(self, spec: OrderSpec) -> list[ShipmentEventRow]:
        hub = self.rng.choice(HUBS)
        start = spec.placed_days_ago - 1
        events = [
            ShipmentEventRow(
                status="label_created", location="Seller warehouse", scanned_at=self._at(start, 9)
            )
        ]
        events.append(
            ShipmentEventRow(status="in_transit", location=hub, scanned_at=self._at(start - 1, 20))
        )
        if spec.shipment_status == "delivered" and spec.delivered_days_ago is not None:
            events.append(
                ShipmentEventRow(
                    status="out_for_delivery",
                    location="Local delivery centre",
                    scanned_at=self._at(spec.delivered_days_ago, 8),
                )
            )
            events.append(
                ShipmentEventRow(
                    status="delivered",
                    location="Customer address",
                    scanned_at=self._at(spec.delivered_days_ago, 15),
                )
            )
        return events

    def _filler(self, customers: int, orders: int) -> None:
        for i in range(11, 11 + customers):
            name = self.fake.name()
            self._customer(
                f"C{i:04d}",
                name,
                self.fake.city(),
                self.rng.choice(["regular", "regular", "gold"]),
                self.rng.random() < 0.06,
            )
        skus = list(self.products)
        for n in range(orders):
            placed = self.rng.randint(1, 90)
            delivered = placed - self.rng.randint(2, 7)
            status = "delivered" if delivered >= 0 else "shipped"
            spec = OrderSpec(
                order_no=f"ORD-{200001 + n}",
                customer_no=f"C{self.rng.randint(11, 10 + customers):04d}",
                skus=tuple(self.rng.sample(skus, self.rng.choice([1, 1, 2]))),
                placed_days_ago=placed,
                order_status=status,
                shipment_status="delivered" if status == "delivered" else "in_transit",
                promised_days_ago=max(delivered, -3),
                delivered_days_ago=delivered if status == "delivered" else None,
                payment=self.rng.choice(["UPI", "Credit Card", "Debit Card", "Net Banking", "COD"]),
            )
            self._order(spec)


async def _counts(session: AsyncSession) -> dict[str, int]:
    tables = ["customers", "products", "orders", "order_items", "shipments", "shipment_events"]
    return {
        t: (await session.execute(text(f"SELECT count(*) FROM {t}"))).scalar_one()  # noqa: S608
        for t in tables
    }


async def _run(database: Database, anchor: date, *, reset: bool) -> dict[str, int]:
    try:
        return await seed(database.engine, anchor, reset=reset)
    finally:
        await database.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="order-platform-seed")
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = parser.parse_args()
    settings = Settings()
    anchor = settings.anchor_date or date.today()
    counts = asyncio.run(_run(Database(settings), anchor, reset=args.reset))
    print(f"Seeded (anchor {anchor}): {counts}")
