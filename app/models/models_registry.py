"""Alembic autogenerate 가 모든 도메인 모델을 인식하도록 import.

새 도메인 추가 시 여기에 import 추가 — alembic revision --autogenerate 가 빠뜨리지 않게.
"""
# ruff: noqa: F401
from app.domains.customers.models import Customer
from app.domains.delivery_orders.models import DeliveryOrder
from app.domains.driver.models import DriverLocationPing, DriverPushToken
from app.domains.drivers.models import Driver
from app.domains.files.models import File
from app.domains.legs.models import Leg
from app.domains.locations.models import Location
from app.domains.notifications.models import Notification
from app.domains.rate_settings.models import RateSetting
from app.domains.settlements.models import (
    ExtraCharge,
    Settlement,
    SettlementAuditLog,
)
from app.domains.street_turns.models import StreetTurn
from app.domains.tenants.models import Tenant
from app.domains.terminals.models import Terminal
from app.domains.users.models import User
from app.domains.vessels.models import Vessel
