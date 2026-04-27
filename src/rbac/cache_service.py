# rbac/cache_service.py
from typing import Optional, Iterable, Set, Tuple, List
from redis.asyncio import Redis
import json
from common.const.settings import settings

def _b2s(v): return v.decode() if isinstance(v, (bytes, bytearray)) else v

# ─────────────────────────────────────────────────────────
# TTL 환경설정
# ─────────────────────────────────────────────────────────
_USER_TEAM_TTL = settings.RBAC_USER_TEAM_TTL
_GROUP_CODES_TTL = settings.RBAC_GROUP_CODES_TTL

# ─────────────────────────────────────────────────────────
# Redis 키 규칙
#   USER_TEAM_META: {"permission_group_id": int|null, "is_admin": bool, "version": int|null}
#   GROUP_CODES   : ["PRODUCT_WRITE", "SALES_VIEW", ...]
# ─────────────────────────────────────────────────────────
USER_TEAM_META_KEY      = "rbac:u:{uid}:t:{tid}"
GROUP_CODES_KEY         = "rbac:g:{gid}"
GROUP_EXCLUDED_ATTRS_KEY = "rbac:g:{gid}:excluded_attrs"
TEAM_SCOPE_KEY          = "team:scope:{uid}:{tid}"


# ──────────────── User-Team Meta ────────────────
async def get_user_team_meta(redis: Redis, uid: int, tid: int) -> Optional[Tuple[Optional[int], bool, Optional[int]]]:
    """
    캐시에서 (permission_group_id, is_admin, version) 조회.
    - 실패/파싱오류 시 None → 레포지토리에서 DB 폴백.
    """
    raw = await redis.get(USER_TEAM_META_KEY.format(uid=uid, tid=tid))
    if not raw:
        return None
    try:
        o = json.loads(_b2s(raw))
        return (
            o.get("permission_group_id"),
            bool(o.get("is_admin", False)),
            (o.get("version") if o.get("version") is not None else None),
        )
    except Exception:
        return None


async def set_user_team_meta(redis: Redis, uid: int, tid: int, group_id: Optional[int], is_admin: bool, version: Optional[int]):
    """
    (permission_group_id, is_admin, version) 캐시 저장.
    - 권한 변경/멤버 그룹 이동 시 반드시 invalidate 필요.
    """
    payload = json.dumps({
        "permission_group_id": group_id,
        "is_admin": is_admin,
        "version": version,
    })
    await redis.set(USER_TEAM_META_KEY.format(uid=uid, tid=tid), payload, ex=_USER_TEAM_TTL)


async def invalidate_user_team_meta(redis: Redis, uid: int, tid: int):
    """사용자-팀 권한 메타 캐시 무효화 (단일)."""
    await redis.delete(USER_TEAM_META_KEY.format(uid=uid, tid=tid))


async def bulk_invalidate_user_team_meta(redis: Redis, pairs: List[Tuple[int, int]]):
    """
    사용자-팀 권한 메타 캐시 벌크 무효화 (Pipeline).
    
    - 한 번의 네트워크 왕복으로 N개 키 삭제
    - 성능: 100명 기준 ~100ms → ~2ms
    
    Args:
        redis: Redis 클라이언트
        pairs: [(user_id, team_id), ...] 리스트
    """
    if not pairs:
        return
    
    keys = [USER_TEAM_META_KEY.format(uid=uid, tid=tid) for uid, tid in pairs]
    
    # UNLINK는 DELETE보다 빠름 (비동기 삭제)
    # 키를 즉시 접근 불가로 만들고, 실제 메모리 해제는 백그라운드 처리
    await redis.unlink(*keys)


# ──────────────── Team Scope (멤버십 확인 캐시) ────────────────
async def invalidate_team_scope(redis: Redis, uid: int, tid: int):
    """팀 소속 확인 캐시 무효화 (멤버 제거/탈퇴 시 호출)."""
    await redis.delete(TEAM_SCOPE_KEY.format(uid=uid, tid=tid))


# ──────────────── Group Codes ────────────────
async def get_group_codes(redis: Redis, gid: int) -> Optional[Set[str]]:
    """
    그룹의 권한 코드 세트 조회.
    - None이면 캐시 미스 → DB 폴백 후 재세팅.
    """
    raw = await redis.get(GROUP_CODES_KEY.format(gid=gid))
    if not raw:
        return None
    try:
        arr = json.loads(_b2s(raw))
        return set(arr)
    except Exception:
        return None


async def set_group_codes(redis: Redis, gid: int, codes: Iterable[str]):
    """그룹 코드 세트 캐시 저장(전체 교체)."""
    await redis.set(GROUP_CODES_KEY.format(gid=gid), json.dumps(list(codes)), ex=_GROUP_CODES_TTL)


async def invalidate_group_codes(redis: Redis, gid: int):
    """그룹 코드 세트 캐시 무효화. (코드 추가/삭제/교체 후 호출)"""
    await redis.delete(GROUP_CODES_KEY.format(gid=gid))


# ──────────────── Group Excluded Attributes ────────────────
async def get_group_excluded_attrs(redis: Redis, gid: int) -> Optional[Set[int]]:
    """
    그룹의 제외 속성 ID 세트 조회.
    - None이면 캐시 미스 → DB 폴백 후 재세팅.
    """
    raw = await redis.get(GROUP_EXCLUDED_ATTRS_KEY.format(gid=gid))
    if not raw:
        return None
    try:
        arr = json.loads(_b2s(raw))
        return set(arr)
    except Exception:
        return None


async def set_group_excluded_attrs(redis: Redis, gid: int, ids: Iterable[int]):
    """그룹 제외 속성 ID 세트 캐시 저장."""
    await redis.set(GROUP_EXCLUDED_ATTRS_KEY.format(gid=gid), json.dumps(list(ids)), ex=_GROUP_CODES_TTL)


async def invalidate_group_excluded_attrs(redis: Redis, gid: int):
    """그룹 제외 속성 ID 세트 캐시 무효화."""
    await redis.delete(GROUP_EXCLUDED_ATTRS_KEY.format(gid=gid))


async def bulk_invalidate_group_codes(redis: Redis, group_ids: List[int]):
    """
    그룹 코드 세트 캐시 벌크 무효화.
    
    Args:
        redis: Redis 클라이언트
        group_ids: 그룹 ID 리스트
    """
    if not group_ids:
        return
    
    keys = [GROUP_CODES_KEY.format(gid=gid) for gid in group_ids]
    await redis.unlink(*keys)