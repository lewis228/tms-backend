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

# ── TMS Master Data (Phase B) ────────────────────────────────
from customer.model import CustomerModel  # noqa: F401
from terminal.model import TerminalModel  # noqa: F401
from vessel.model import VesselModel  # noqa: F401
from location.model import LocationModel  # noqa: F401
from driver.model import DriverModel  # noqa: F401

# ── TMS D/O / Leg / Settlement (Phase C) ─────────────────────
from rate_setting.model import RateSettingModel  # noqa: F401
from delivery_order.model import DeliveryOrderModel  # noqa: F401
from leg.model import LegModel  # noqa: F401
from street_turn.model import StreetTurnModel  # noqa: F401
from settlement.model import (  # noqa: F401
    SettlementModel,
    ExtraChargeModel,
    SettlementAuditLogModel,
)

# ── TMS Phase D — Notification ──────────────────────────────
from notification.model import NotificationModel  # noqa: F401

# ── TMS Phase F — Driver mobile satellite ───────────────────
from location_ping.model import LocationPingModel  # noqa: F401
from push_token.model import PushTokenModel  # noqa: F401

# ── API Keys ────────────────────────────────────────────────
from api_key.model import ApiKeyModel  # noqa: F401
