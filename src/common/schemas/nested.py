# src/common/schemas/nested.py
"""
공통 중첩 스키마 (Nested Schemas)

각 도메인의 Response 스키마에서 중첩 객체로 사용되는 스키마들.
- 모델 컬럼명과 일치해야 from_attributes=True 자동변환 가능
- 네이밍 규칙: XXXNestedSchema
- url 등 서비스에서 주입하는 필드는 Optional로 선언
"""
from __future__ import annotations
from typing import Optional, List, Any
from decimal import Decimal

from common.schemas.base import ResponseSchema


# ═══════════════════════════════════════════════════════════════
# Location (위치)
# - 사용처: inbound, outbound, adjust, transfer, return_inbound, product, stock
# - 최대 필드: id, name, note (product의 StockRowResponseSchema에서 사용)
# ═══════════════════════════════════════════════════════════════

class LocationNestedSchema(ResponseSchema):
    """
    LocationModel 중첩 스키마
    - 모델 컬럼: id, name, note, tenant_id, is_active, ...
    - is_active: 소프트 삭제 여부 (False면 취소선 표시)
    """
    id: int
    name: str
    note: Optional[str] = None
    is_active: bool = True


# ═══════════════════════════════════════════════════════════════
# FileAsset (파일)
# - 사용처: inbound, outbound, transfer, return_inbound, product, user
# - 최대 필드: product의 FileAssetResponseSchema 기준
# - url: 서비스에서 presigned URL 주입 (모델에 없음)
#  UserNestedSchema보다 먼저 선언 (순환 참조 방지)
# ═══════════════════════════════════════════════════════════════

class FileNestedSchema(ResponseSchema):
    """
    FileAssetModel 중첩 스키마
    - 모델 컬럼: id, domain, object_id, subdir, filename, size, mime, is_public, logical_path, ...
    - url: 서비스에서 presigned URL 주입 (모델에 없는 확장 필드)
    """
    id: int
    domain: str
    object_id: int
    subdir: str
    filename: str
    size: int
    mime: str
    is_public: bool
    logical_path: str
    url: Optional[str] = None  # 서비스에서 서명 URL 주입


# ═══════════════════════════════════════════════════════════════
# User (사용자)
# - 사용처: inbound, outbound, adjust, transfer, return_inbound, team, history
# ═══════════════════════════════════════════════════════════════

class UserNestedSchema(ResponseSchema):
    """
    UserModel 중첩 스키마 (기본)
    - 모델 컬럼: id, email, password, role, name, is_active, ...
    - password는 응답에서 제외
    """
    id: int
    email: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None


class UserNestedWithFilesSchema(UserNestedSchema):
    """
    UserModel 중첩 스키마 (프로필 이미지 포함)
    - 삭제된 위치 등 프로필 이미지가 필요한 곳에서 사용
    - files: 프로필 이미지 (relationship)
    """
    files: List[FileNestedSchema] = []


# ═══════════════════════════════════════════════════════════════
# Partner (거래처)
# - 사용처: inbound, outbound, return_inbound
# - 최대 필드: id, name
# ═══════════════════════════════════════════════════════════════

class PartnerNestedSchema(ResponseSchema):
    """
    PartnerModel 중첩 스키마
    - 모델 컬럼: id, name, type, phone, email, address, memo, is_favorite, is_active, ...
    - is_active: 소프트 삭제 여부 (False면 취소선 표시)
    """
    id: int
    name: str
    is_active: bool = True


# ═══════════════════════════════════════════════════════════════
# Product (제품) - IO 라인 중첩용
# - 사용처: inbound, outbound, transfer, return_inbound (라인의 product 중첩)
# - 최대 필드: id, sku, name, barcode, files
# ═══════════════════════════════════════════════════════════════

class ProductNestedSchema(ResponseSchema):
    """
    ProductModel 중첩 스키마 (IO 라인용)
    - 모델 컬럼: id, sku, name, barcode, is_bundle, sale_price, purchase_price, ...
    - files: 관계(relationship)로 연결된 FileAssetModel 리스트
    """
    id: int
    sku: str
    name: str
    barcode: Optional[str] = None
    is_bundle: bool = False
    files: List[FileNestedSchema] = []
    is_active: bool = True


# NOTE: ProductLineNestedSchema는 아래 BundleComponentNestedSchema 뒤에 선언됨
#       (bundle_components 필드가 BundleComponentNestedSchema를 참조하므로)


# ═══════════════════════════════════════════════════════════════
# PermissionGroup (권한 그룹)
# - 사용처: team
# - 최대 필드: id, name
# ═══════════════════════════════════════════════════════════════

class PermissionGroupNestedSchema(ResponseSchema):
    """
    PermissionGroupModel 중첩 스키마
    - 모델 컬럼: id, name, ...
    """
    id: int
    name: str


# ═══════════════════════════════════════════════════════════════
# AttributeDef (속성 정의)
# - 사용처: product (AttributeValue 내 중첩)
# - 최대 필드: id, name, kind, sort_order
# ═══════════════════════════════════════════════════════════════

class AttributeDefNestedSchema(ResponseSchema):
    """
    AttributeDefModel 중첩 스키마
    - 모델 컬럼: id, name, kind, sort_order, tenant_id, ...
    """
    id: int
    name: str
    kind: str  # AttributeKind Enum → .value 직렬화
    sort_order: int


# ═══════════════════════════════════════════════════════════════
# AttributeValue (속성 값)
# - 사용처: product
# - 최대 필드: id, product_id, attribute_id, value, attribute(중첩)
# ═══════════════════════════════════════════════════════════════

class AttributeValueNestedSchema(ResponseSchema):
    """
    AttributeValueModel 중첩 스키마
    - 모델 컬럼: id, product_id, attribute_id, value, tenant_id, ...
    - attribute: 관계(relationship)로 연결된 AttributeDefModel
    """
    id: int
    product_id: int
    attribute_id: int
    value: Any
    attribute: Optional[AttributeDefNestedSchema] = None


# ═══════════════════════════════════════════════════════════════
# Stock (재고)
# - 사용처: product
# - 최대 필드: id, product_id, location_id, qty, location(중첩)
#  version 필드 제거됨
# ═══════════════════════════════════════════════════════════════

class StockNestedSchema(ResponseSchema):
    """
    StockModel 중첩 스키마
    - 모델 컬럼: id, product_id, location_id, qty, tenant_id, ...
    - location: 관계(relationship)로 연결된 LocationModel
    
     version 필드 제거됨 (StockLine이 현재 유효한 변동만 보관)
    """
    id: int
    product_id: int
    location_id: int
    qty: Decimal
    location: Optional[LocationNestedSchema] = None


# ═══════════════════════════════════════════════════════════════
# BundleComponentLine (번들 구성품)
# - 사용처: product
# - 최대 필드: id, bundle_product_id, component_product_id, qty, component_product(중첩)
# ═══════════════════════════════════════════════════════════════

class ProductBasicNestedSchema(ResponseSchema):
    """
    ProductModel 기본 중첩 스키마 (번들 구성품용)
    - BundleComponentLine의 component_product에서 사용
    - 가격, 속성, 파일, 활성 상태 포함
    """
    id: int
    sku: str
    name: str
    barcode: Optional[str] = None
    is_bundle: bool
    is_active: bool = True
    sale_price: Decimal
    purchase_price: Decimal
    files: List[FileNestedSchema] = []
    attributes: List[AttributeValueNestedSchema] = []


class BundleComponentNestedSchema(ResponseSchema):
    """
    BundleProductLineModel 중첩 스키마
    - 모델 컬럼: id, bundle_product_id, component_product_id, qty, tenant_id, ...
    - component_product: 관계(relationship)로 연결된 ProductModel
    """
    id: int
    bundle_product_id: int
    component_product_id: int
    qty: Decimal
    component_product: Optional[ProductBasicNestedSchema] = None


# ═══════════════════════════════════════════════════════════════
# Product Line (제품) - Purchase/Sales/Returns 라인 전용
# - 사용처: purchase, sales, returns (라인의 product 중첩)
# - ProductNestedSchema + 가격/속성/번들구성 포함
# - 디테일·수정 페이지에서 productProvider 의존 제거 목적
# ═══════════════════════════════════════════════════════════════

class ProductLineNestedSchema(ProductNestedSchema):
    """
    Purchase/Sales/Returns 라인 전용 풍부한 제품 스키마.
    ProductNestedSchema를 상속하고 가격, 속성, 번들 구성품을 추가.
    """
    memo: Optional[str] = None
    sale_price: Optional[Decimal] = None
    purchase_price: Optional[Decimal] = None
    attributes: List[AttributeValueNestedSchema] = []
    bundle_components: List[BundleComponentNestedSchema] = []


# ═══════════════════════════════════════════════════════════════
# Purchase (발주서)
# - 사용처: inbound (입고 헤더의 purchase 중첩)
# - 최대 필드: id, purchase_no, is_active
# ═══════════════════════════════════════════════════════════════

class PurchaseNestedSchema(ResponseSchema):
    """
    PurchaseModel 중첩 스키마
    - 모델 컬럼: id, purchase_no, is_active, ...
    - is_active: 소프트 삭제 여부 (False면 취소선 표시)
    """
    id: int
    purchase_no: str
    is_active: bool


# ═══════════════════════════════════════════════════════════════
# Sales (판매서)
# - 사용처: outbound (출고 헤더의 sales 중첩)
# - 최대 필드: id, sales_no, is_active
# ═══════════════════════════════════════════════════════════════

class SalesNestedSchema(ResponseSchema):
    """
    SalesModel 중첩 스키마
    - 모델 컬럼: id, sales_no, is_active, ...
    - is_active: 소프트 삭제 여부 (False면 취소선 표시)
    """
    id: int
    sales_no: str
    is_active: bool


# ═══════════════════════════════════════════════════════════════
# Return (반품서)
# - 사용처: return_inbound (반품입고 헤더의 return_ 중첩)
# - 최대 필드: id, return_no, sales_id, is_active, sales(중첩)
# ═══════════════════════════════════════════════════════════════

class ReturnNestedSchema(ResponseSchema):
    """
    ReturnModel 중첩 스키마
    - 모델 컬럼: id, return_no, sales_id, is_active, ...
    - is_active: 소프트 삭제 여부 (False면 취소선 표시)
    - sales: 관계(relationship)로 연결된 SalesModel (원래 판매서 정보)
    """
    id: int
    return_no: str
    sales_id: int
    is_active: bool
    sales: Optional[SalesNestedSchema] = None