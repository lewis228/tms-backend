# common/model/models_registry.py — Alembic autogenerate 가 metadata 인식하도록 import
"""
모든 도메인 모델을 한 곳에서 import. side-effect 로 Base.metadata 에 테이블 등록.

migrations/env.py 가 이 모듈을 import 해서 Base.metadata 를 가져감.

Phase A — 시스템 도메인 (auth/user/team/rbac/file) 만.
Phase B+ 에서 TMS 도메인 추가.
"""
from common.model.base_model import Base  # noqa: F401  (re-export — env.py 가 사용)

# ── 시스템 도메인 ─────────────────────────────────────────────
from user.model import UserModel  # noqa: F401
from team.model import TeamModel, UserTeamModel  # noqa: F401
from rbac.model import (  # noqa: F401
    PermissionModel,
    PermissionGroupModel,
    PermissionGroupPermission,
)
from file.model import FileAssetModel  # noqa: F401
from zip_code.model import ZipCodeModel  # noqa: F401  (전역 zip 마스터)

# ── TMS Master Data (Phase B) ────────────────────────────────
from customer.model import CustomerModel  # noqa: F401
from terminal.model import TerminalModel  # noqa: F401
from vessel.model import VesselModel  # noqa: F401
from location.model import LocationModel  # noqa: F401
from driver.model import DriverModel  # noqa: F401
from truck.model import TruckModel  # noqa: F401
from equipment_pool.model import EquipmentPoolModel  # noqa: F401
from chassis.model import ChassisModel  # noqa: F401

# ── TMS D/O / Leg (Phase C) ──────────────────────────────────
from delivery_order.model import DeliveryOrderModel, DeliveryOrderAddonModel  # noqa: F401
from container.model import ContainerModel, ContainerEventModel  # noqa: F401
from leg.model import LegModel  # noqa: F401
from chassis_event.model import ChassisEventModel  # noqa: F401
from street_turn.model import StreetTurnModel  # noqa: F401

# ── TMS Phase D — Notification ──────────────────────────────
from notification.model import NotificationModel  # noqa: F401

# ── TMS Phase F — Driver mobile satellite ───────────────────
from location_ping.model import LocationPingModel  # noqa: F401
from push_token.model import PushTokenModel  # noqa: F401

# ── API Keys ────────────────────────────────────────────────
from api_key.model import ApiKeyModel  # noqa: F401

# ── TMS 재설계 (Confluence 기준) — Rate 서브시스템 ───────────
from rate_point.model import RatePointModel  # noqa: F401
from rate_group.model import RateGroupModel  # noqa: F401
from driver_rate_assignment.model import DriverRateAssignmentModel  # noqa: F401
from rate_zone.model import RateZoneModel, RateZoneMemberModel  # noqa: F401
from rate_sheet.model import RateSheetModel, RateEntryModel, RateEntryHistoryModel  # noqa: F401
from rate_multiplier.model import RateMultiplierModel  # noqa: F401
from load_type_template.model import LoadTypeTemplateModel, LoadTypeTemplateStepModel  # noqa: F401
from addon.model import AddonModel  # noqa: F401
from audit_log.model import AuditLogModel  # noqa: F401
from leg_layer.model import LegAddonModel  # noqa: F401
from payroll.model import PayrollSettlementModel, PayrollLineModel, PayrollChargeModel  # noqa: F401
from invoice.model import InvoiceModel, InvoiceLineModel  # noqa: F401
from dual_transaction.model import DualTransactionModel  # noqa: F401

# ── TMS Phase I-A (Container-First v3) ───────────────────────
from container_stop.model import ContainerStopModel  # noqa: F401
from leg_driver_segment.model import LegDriverSegmentModel  # noqa: F401

# ── Demo (Driver mobile) — 채팅 ──────────────────────────────
from chat.model import ChatMessageModel  # noqa: F401
