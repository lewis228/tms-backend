from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from common.schemas.base import ResponseSchema
from carrier.schemas.response import CarrierResponseSchema
from location.schemas.response import LocationResponseSchema
from ocean.container.schemas.response import ContainerResponseSchema
from ocean.container_event.schemas.response import ContainerEventResponseSchema
from tag.schemas.response import TagResponseSchema
from customer.schemas.response import CustomerResponseSchema


class ShipmentResponseSchema(ResponseSchema):
    id: int
    team_id: int
    mbl: str
    carrier_id: int
    # Nested carrier resolved from carrier_id. Always present on a valid shipment
    # because carrier_id is NOT NULL and FK-enforced.
    carrier: Optional[CarrierResponseSchema] = None
    status: str
    vessel_name: Optional[str] = None
    vessel_id: Optional[int] = None
    voyage_number: Optional[str] = None
    pol_location_id: Optional[int] = None
    pod_location_id: Optional[int] = None
    pol_location: Optional[LocationResponseSchema] = None
    pod_location: Optional[LocationResponseSchema] = None
    etd: Optional[datetime] = None
    eta: Optional[datetime] = None
    confidence: Optional[str] = None
    tracking_frequency: Optional[str] = None
    next_scrape_at: Optional[datetime] = None
    # Customer is a single-assignment FK to the team-scoped ``customers`` master.
    # Null when not set. Frontend renders customer.name.
    customer_id: Optional[int] = None
    customer: Optional[CustomerResponseSchema] = None
    # Ref numbers flattened to a string array on the wire. The ORM side stores
    # them as RefNumberModel rows; a model validator in the service layer
    # produces this list from the ``ref_numbers`` relationship.
    ref_numbers: List[str] = []
    tags: List[TagResponseSchema] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ShipmentDetailResponseSchema(ShipmentResponseSchema):
    containers: List[ContainerResponseSchema] = []
    events: List[ContainerEventResponseSchema] = []


class TrackResponseSchema(ResponseSchema):
    """GET /api/v1/track 응답"""
    shipment: ShipmentResponseSchema
    containers: List[ContainerResponseSchema] = []
    events: List[ContainerEventResponseSchema] = []
