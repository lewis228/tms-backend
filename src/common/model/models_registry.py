# common/model/models_registry.py
"""모든 모델을 SQLAlchemy metadata에 등록"""
from common.model.base_model import Base

# Auth / User
from user.model import UserModel
from team.model import TeamModel, UserTeamModel

# RBAC
from rbac.model import PermissionModel, PermissionGroupModel, PermissionGroupPermission

# File
from file.model import FileAssetModel

# API keys (team-scoped, replaces the old Company-based integration channel)
from api_key.model import ApiKeyModel

# Tags (team-scoped, attached to shipments across domains)
from tag.model import TagModel, OceanShipmentTagModel

# Customers (team-scoped, single-assignment on shipments — M:1 to shipment)
from customer.model import CustomerModel

# Carrier master catalogue (global — not team-scoped)
from carrier.model import CarrierModel

# Location master (global — shared by ocean / air / rail domains)
from location.model import LocationModel, LocationAliasModel

# Vessel master + latest position (global — not team-scoped; many teams/MBLs
# can reference the same ship. Team isolation happens via ocean_shipments
# joining on vessel_id).
from vessel.model import VesselModel, VesselPositionModel

# Tracking domain
from ocean.shipment.model import ShipmentModel
from ocean.container.model import ContainerModel
from ocean.container_event.model import ContainerEventModel
from ocean.scrape_log.model import ScrapeLogModel
from ocean.ref_number.model import RefNumberModel
