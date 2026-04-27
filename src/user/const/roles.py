from enum import StrEnum


class RolesEnum(StrEnum):
    """플랫폼 + team 통합 역할.

    SUPER_ADMIN: 플랫폼 운영자 (team 없음, X-Team-Id 로 cross-team)
    ADMIN: team 의 사장. 모든 RBAC 권한 통과 (admin_group)
    DISPATCHER: team 의 운영자. RBAC 그룹 별 권한
    DRIVER: 모바일 앱 사용자

    StrEnum 사용:
    - str(RolesEnum.DRIVER) == "DRIVER" 보장 ((str, Enum) 다중상속은 "RolesEnum.DRIVER" 반환)
    - RolesEnum.DRIVER == "DRIVER" 도 True
    - 기존의 .value 비교 코드는 그대로 유지 (가장 안전)
    """
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    DISPATCHER = "DISPATCHER"
    DRIVER = "DRIVER"
