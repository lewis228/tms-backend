# src/team/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncWithAllIdsResponse
from database.dependencies import get_read_db, get_write_db
from cache.dependencies import get_write_redis

from auth.tokens.access_token import access_token
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema as AuthUserResponseSchema  # 충돌 방지 alias

from rbac.dependencies.guards import permission_guard
from rbac.const.const import (
    TEAM_RENAME, TEAM_DELETE,
    TEAM_MEMBER_INVITE, TEAM_MEMBER_REMOVE, TEAM_MEMBER_PERMISSION_ASSIGN,
)

from team.service import TeamService
from team.schemas.request import (
    PaginateTeamMemberRequestSchema,
    PaginateTeamRequestSchema,
    TeamCreateRequestSchema,
    TeamRenameRequestSchema,
    InviteMemberRequestSchema,
    AssignPermissionGroupRequestSchema,
    OnboardingUpdateRequestSchema,
    TeamSettingsUpdateRequestSchema,
)
from file.service import FileService
from file.schemas.request import UploadUrlRequestSchema
from file.schemas.response import UploadUrlResponseSchema

from team.schemas.response import (
    TeamListItemResponseSchema,
    UserTeamResponseSchema,
    TeamDetailResponseSchema,
    TeamRenameResponseSchema,
    TeamDeleteResponseSchema,
    TeamReactivateResponseSchema,
    TeamMemberInviteResponseSchema,
    TeamMemberRemoveResponseSchema,
    TeamMemberPermissionResponseSchema,
    OnboardingUpdateResponseSchema,
    TeamUsageStatsResponseSchema,
    TimezoneItemSchema,
)
from team.service import get_timezone_list


router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


# ─────────────────────────────────────────────────────────
# ▼ 시간대 목록 (참조 데이터 — team_id 불필요)
# ─────────────────────────────────────────────────────────
@router.get("/timezones", response_model=list[TimezoneItemSchema])
async def list_timezones(
    _1: None = Depends(access_token),
):
    """IANA 시간대 전체 목록 반환 (GMT offset 정렬)"""
    return get_timezone_list()


# ─────────────────────────────────────────────────────────
# ▼ 커서 페이지네이션: 마이 팀 목록
# ─────────────────────────────────────────────────────────
@router.get("/my-teams", response_model=CursorPaginationResult[TeamListItemResponseSchema])
async def get_my_teams_cursor(
    request: PaginateTeamRequestSchema = Depends(),
    _1: None = Depends(access_token),
    me: AuthUserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_read_db),  #  SELECT → get_read_db
):
    svc = TeamService(db)
    return await svc.list_my_teams_paginated(int(me.id), request)


# ─────────────────────────────────────────────────────────
# ▼ 단일 팀 상세 화면 (product 패턴 통일)
# ─────────────────────────────────────────────────────────
@router.get("/{team_id}", response_model=TeamDetailResponseSchema)
async def get_team_detail(
    team_id: int,
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_read_db),  #  SELECT → get_read_db
):
    svc = TeamService(db)
    return await svc.get_team(team_id)


# ─────────────────────────────────────────────────────────
# ▼ 팀 멤버 목록 커서 페이지네이션
# ─────────────────────────────────────────────────────────
@router.get("/{team_id}/members", response_model=CursorPaginationResult[UserTeamResponseSchema])
async def list_team_members(
    team_id: int,
    request: PaginateTeamMemberRequestSchema = Depends(),
    _1: None = Depends(access_token),
    me: AuthUserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_read_db),  #  SELECT → get_read_db
):
    svc = TeamService(db)
    return await svc.list_team_members_paginated(
        team_id=team_id,
        request=request,
        actor_user_id=int(me.id),
    )


# ─────────────────────────────────────────────────────────
# ▼ 팀 멤버 Delta Sync (hard-delete → all_ids)
# ─────────────────────────────────────────────────────────
@router.get("/{team_id}/members/sync", response_model=SyncWithAllIdsResponse[UserTeamResponseSchema])
async def sync_team_members(
    team_id: int,
    since: str,
    _1: None = Depends(access_token),
    me: AuthUserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_read_db),
):
    """팀 멤버 Delta Sync (since 이후 변경분 + 전체 활성 ID)"""
    svc = TeamService(db)
    return await svc.sync_members_delta(
        team_id=team_id,
        since_str=since,
        actor_user_id=int(me.id),
    )


# ─────────────────────────────────────────────────────────
# 생성 / 수정 / 삭제
# ─────────────────────────────────────────────────────────
@router.post("", response_model=TeamDetailResponseSchema)
async def create_team(
    payload: TeamCreateRequestSchema,
    _1: None = Depends(access_token),
    me: AuthUserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),  #  INSERT → get_write_db
):
    svc = TeamService(db)
    return await svc.create_team(name=payload.name, creator_user_id=int(me.id))


@router.put("/{team_id}", response_model=TeamRenameResponseSchema)
async def rename_team(
    team_id: int,
    payload: TeamRenameRequestSchema = None,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TEAM_RENAME)),
    db: AsyncSession = Depends(get_write_db),
    me: AuthUserResponseSchema = Depends(get_current_user),
):
    """팀 이름 변경"""
    svc = TeamService(db)
    return await svc.rename_team(team_id=team_id, name=payload.name, actor_user_id=int(me.id))


@router.delete("/{team_id}", response_model=TeamDeleteResponseSchema)
async def delete_team(
    team_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TEAM_DELETE)),
    db: AsyncSession = Depends(get_write_db),
    me: AuthUserResponseSchema = Depends(get_current_user),
):
    """
    팀 삭제 (소프트)
    - 비활성화 후 purge_at 예약
    """
    svc = TeamService(db)
    return await svc.delete_team(team_id=team_id, actor_user_id=int(me.id))


@router.post("/{team_id}/reactivate", response_model=TeamReactivateResponseSchema)
async def reactivate_team(
    team_id: int,
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_write_db),  #  UPDATE → get_write_db
):
    """비활성화된 팀 재활성화"""
    svc = TeamService(db)
    return await svc.reactivate_team(team_id=team_id)


@router.post("/{team_id}/members", response_model=TeamMemberInviteResponseSchema)
async def invite_member(
    team_id: int,
    payload: InviteMemberRequestSchema = None,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TEAM_MEMBER_INVITE)),
    db: AsyncSession = Depends(get_write_db),  #  INSERT → get_write_db
    redis: Redis = Depends(get_write_redis),   #  캐시 무효화 → get_write_redis
):
    """팀 멤버 초대"""
    svc = TeamService(db, redis)
    return await svc.invite_member(
        team_id=team_id,
        user_id=payload.user_id,
        permission_group_id=payload.permission_group_id,
    )


@router.delete("/{team_id}/members/{user_id}", response_model=TeamMemberRemoveResponseSchema)
async def remove_member(
    team_id: int,
    user_id: int = None,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TEAM_MEMBER_REMOVE)),
    db: AsyncSession = Depends(get_write_db),  #  DELETE → get_write_db
    redis: Redis = Depends(get_write_redis),   #  캐시 무효화 → get_write_redis
):
    """팀 멤버 제거"""
    svc = TeamService(db, redis)
    return await svc.remove_member(team_id=team_id, target_user_id=user_id)


@router.post("/{team_id}/leave", response_model=TeamMemberRemoveResponseSchema)
async def leave_team(
    team_id: int,
    _1: None = Depends(access_token),
    me: AuthUserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),  #  DELETE → get_write_db
    redis: Redis = Depends(get_write_redis),   #  캐시 무효화 → get_write_redis
):
    """팀 탈퇴 (본인)"""
    svc = TeamService(db, redis)
    return await svc.leave_team(team_id=team_id, actor_user_id=int(me.id))


@router.put("/{team_id}/members/{user_id}/permission-group", response_model=TeamMemberPermissionResponseSchema)
async def assign_permission_group(
    team_id: int,
    user_id: int = None,
    payload: AssignPermissionGroupRequestSchema = None,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TEAM_MEMBER_PERMISSION_ASSIGN)),
    db: AsyncSession = Depends(get_write_db),  #  UPDATE → get_write_db
    redis: Redis = Depends(get_write_redis),   #  캐시 무효화 → get_write_redis
):
    """멤버 권한 그룹 변경"""
    svc = TeamService(db, redis)
    return await svc.assign_permission_group(
        team_id=team_id, target_user_id=user_id, permission_group_id=payload.permission_group_id
    )


# ─────────────────────────────────────────────────────────
# ▼ 팀 이미지 업로드용 Presigned URL 발급
# ─────────────────────────────────────────────────────────
@router.post("/{team_id}/upload-urls", response_model=UploadUrlResponseSchema)
async def get_team_upload_urls(
    team_id: int,
    body: UploadUrlRequestSchema,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TEAM_RENAME)),
    db: AsyncSession = Depends(get_read_db),
):
    """팀 이미지 업로드용 Presigned URL 발급"""
    svc = FileService(db)
    token, files = svc.generate_upload_urls(body.filenames)
    return UploadUrlResponseSchema(token=token, files=files)


# ─────────────────────────────────────────────────────────
# ▼ 팀 설정 업데이트
# ─────────────────────────────────────────────────────────
@router.patch("/{team_id}/settings", response_model=TeamDetailResponseSchema)
async def update_team_settings(
    team_id: int,
    payload: TeamSettingsUpdateRequestSchema,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TEAM_RENAME)),
    db: AsyncSession = Depends(get_write_db),
    me: AuthUserResponseSchema = Depends(get_current_user),
):
    """팀 설정 업데이트 (전달된 필드만 반영)"""
    svc = TeamService(db)
    return await svc.update_team_settings(team_id=team_id, payload=payload, actor_user_id=int(me.id))


# ─────────────────────────────────────────────────────────
# ▼ 팀 사용량 통계
# ─────────────────────────────────────────────────────────
@router.get("/{team_id}/usage-stats", response_model=TeamUsageStatsResponseSchema)
async def get_team_usage_stats(
    team_id: int,
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_read_db),
):
    """팀 사용량 통계 조회"""
    svc = TeamService(db)
    return await svc.get_usage_stats(team_id)


# ─────────────────────────────────────────────────────────
# ▼ 온보딩 상태 업데이트
# ─────────────────────────────────────────────────────────
@router.patch("/{team_id}/onboarding", response_model=OnboardingUpdateResponseSchema)
async def update_onboarding(
    team_id: int,
    payload: OnboardingUpdateRequestSchema,
    _1: None = Depends(access_token),
    db: AsyncSession = Depends(get_write_db),
):
    """온보딩 상태 업데이트 (팀 멤버 누구나 가능)"""
    svc = TeamService(db)
    return await svc.update_onboarding(team_id=team_id, payload=payload)


