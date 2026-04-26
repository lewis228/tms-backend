from enum import Enum


class RolesEnum(str, Enum):
    """플랫폼 + tenant 통합 역할.

    SUPER_ADMIN: 플랫폼 운영자 (tenant 없음, X-Tenant-Id 로 cross-tenant)
    ADMIN: tenant 의 사장. 모든 RBAC 권한 통과 (admin_group)
    DISPATCHER: tenant 의 운영자. RBAC 그룹 별 권한
    DRIVER: 모바일 앱 사용자
    """
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    DISPATCHER = "DISPATCHER"
    DRIVER = "DRIVER"
