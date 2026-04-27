# src/file/repository.py
from __future__ import annotations
from typing import Iterable, Sequence, Optional
from sqlalchemy import select, delete, update
from sqlalchemy.orm import load_only
from sqlalchemy.ext.asyncio import AsyncSession

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.service import CommonService
from file.model import FileAssetModel
from file.const.domains import FileDomain
from file.schemas.request import PaginateFileListRequestSchema


class FileRepository:
    """
    파일 메타(FileAssetModel) 전용 레포지토리 (쿼리/CRUD).
    
     team_id=None 지원:
    - User 도메인은 team_id=NULL로 저장
    - 조회/삭제 시 team_id=None이면 IS NULL 조건 사용
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.common = CommonService()

    # ─────────────────────────────────────────────────────────────
    # team_id 조건 헬퍼 (NULL 처리)
    # ─────────────────────────────────────────────────────────────
    def _team_id_condition(self, team_id: Optional[int]):
        """
        team_id 조건 생성 (None이면 IS NULL)
        
        사용: stmt.where(self._team_id_condition(team_id))
        """
        if team_id is not None:
            return FileAssetModel.team_id == team_id
        else:
            return FileAssetModel.team_id.is_(None)

    # ─────────────────────────────────────────────────────────────
    # 커서 페이지네이션: 도메인/오브젝트/서브디렉토리 기준 경량 목록
    # ─────────────────────────────────────────────────────────────
    async def list_files_paginated(
        self, *, team_id: int, request: PaginateFileListRequestSchema
    ) -> CursorPaginationResult[FileAssetModel]:
        base = (
            select(FileAssetModel)
            .where(
                FileAssetModel.team_id == team_id,
                FileAssetModel.domain == request.domain,
                FileAssetModel.object_id == request.object_id,
            )
            .options(
                load_only(
                    FileAssetModel.id,
                    FileAssetModel.team_id,
                    FileAssetModel.domain,
                    FileAssetModel.object_id,
                    FileAssetModel.subdir,
                    FileAssetModel.filename,
                    FileAssetModel.size,
                    FileAssetModel.mime,
                    FileAssetModel.is_public,
                    FileAssetModel.logical_path,
                    FileAssetModel.updated_at,
                )
            )
        )

        if request.subdir is not None:
            base = base.where(FileAssetModel.subdir == request.subdir)

        # 정책상 활성만 노출(필요 시 조정)
        base = base.where(FileAssetModel.is_active.is_(True))

        return await self.common.paginate(
            request=request,
            model=FileAssetModel,
            session=self.db,
            base_query=base,
            path="files/list",
        )

    # ─────────────────────────────────────────────────────────────
    # 단순 목록: 경량 컬럼 로딩
    #  team_id=None 지원
    # ─────────────────────────────────────────────────────────────
    async def list_files(
        self, *, 
        team_id: Optional[int],  #  None 가능
        domain: FileDomain | str, 
        object_id: int, 
        subdir: Optional[str] = None
    ) -> list[FileAssetModel]:
        stmt = (
            select(FileAssetModel)
            .where(
                self._team_id_condition(team_id),  #  NULL 처리
                FileAssetModel.domain == domain,
                FileAssetModel.object_id == object_id,
            )
            .options(
                load_only(
                    FileAssetModel.id,
                    FileAssetModel.team_id,
                    FileAssetModel.domain,
                    FileAssetModel.object_id,
                    FileAssetModel.subdir,
                    FileAssetModel.filename,
                    FileAssetModel.size,
                    FileAssetModel.mime,
                    FileAssetModel.is_public,
                    FileAssetModel.logical_path,
                    FileAssetModel.updated_at,
                )
            )
        )
        if subdir is not None:
            stmt = stmt.where(FileAssetModel.subdir == subdir)

        res = await self.db.scalars(stmt)
        return list(res)

    # ─────────────────────────────────────────────────────────────
    # 다건 추가: flush/refresh 포함
    # ─────────────────────────────────────────────────────────────
    async def add_files(self, assets: Iterable[FileAssetModel]) -> list[FileAssetModel]:
        out: list[FileAssetModel] = []
        for a in assets:
            self.db.add(a)
            out.append(a)
        await self.db.flush()
        for a in out:
            await self.db.refresh(a)
        return out

    # ─────────────────────────────────────────────────────────────
    # ID 목록으로 선택 (팀 스코프 보장)
    #  team_id=None 지원
    # ─────────────────────────────────────────────────────────────
    async def select_by_ids(
        self, *, 
        team_id: Optional[int],  #  None 가능
        ids: Sequence[int]
    ) -> list[FileAssetModel]:
        if not ids:
            return []
        stmt = (
            select(FileAssetModel)
            .where(
                FileAssetModel.id.in_(ids), 
                self._team_id_condition(team_id)  #  NULL 처리
            )
            .options(
                load_only(
                    FileAssetModel.id,
                    FileAssetModel.team_id,
                    FileAssetModel.domain,
                    FileAssetModel.object_id,
                    FileAssetModel.subdir,
                    FileAssetModel.filename,
                    FileAssetModel.size,
                    FileAssetModel.mime,
                    FileAssetModel.is_public,
                    FileAssetModel.logical_path,
                    FileAssetModel.updated_at,
                )
            )
        )
        res = await self.db.scalars(stmt)
        return list(res)

    # ─────────────────────────────────────────────────────────────
    # 다건 삭제: 메타만 삭제 (파일 시스템은 스케줄러에서 별도 정리)
    #  team_id=None 지원
    # ─────────────────────────────────────────────────────────────
    async def delete_files_by_ids(
        self, *, 
        team_id: Optional[int],  #  None 가능
        ids: Sequence[int]
    ) -> int:
        if not ids:
            return 0
        stmt = delete(FileAssetModel).where(
            FileAssetModel.id.in_(ids), 
            self._team_id_condition(team_id)  #  NULL 처리
        )
        res = await self.db.execute(stmt)
        return res.rowcount or 0

    # ─────────────────────────────────────────────────────────────
    # 도메인/오브젝트 스코프 전체 삭제 (메타만)
    #  team_id=None 지원
    # ─────────────────────────────────────────────────────────────
    async def delete_scope(
        self, *, 
        team_id: Optional[int],  #  None 가능
        domain: FileDomain | str, 
        object_id: int
    ) -> int:
        stmt = delete(FileAssetModel).where(
            self._team_id_condition(team_id),  #  NULL 처리
            FileAssetModel.domain == domain,
            FileAssetModel.object_id == object_id,
        )
        res = await self.db.execute(stmt)
        return res.rowcount or 0

    # ─────────────────────────────────────────────────────────────
    # 팀 전체 삭제 (메타만) — 퍼지 시 사용 가능
    # ─────────────────────────────────────────────────────────────
    async def delete_all_in_team(self, *, team_id: int) -> int:
        stmt = delete(FileAssetModel).where(FileAssetModel.team_id == team_id)
        res = await self.db.execute(stmt)
        return res.rowcount or 0
    
    # ─────────────────────────────────────────────────────────────
    # 소프트 삭제: 도메인/오브젝트 스코프 전체
    #  team_id=None 지원
    # ─────────────────────────────────────────────────────────────
    async def soft_deactivate_by_object(
        self,
        *,
        team_id: Optional[int],
        domain: FileDomain | str,
        object_id: int,
        actor_user_id: int | None = None,
    ) -> int:
        """
        도메인 객체의 모든 파일 소프트삭제
        
        사용: Product 소프트삭제 시 연관 파일도 소프트삭제
        """
        stmt = (
            update(FileAssetModel)
            .where(
                self._team_id_condition(team_id),
                FileAssetModel.domain == domain,
                FileAssetModel.object_id == object_id,
                FileAssetModel.is_active.is_(True),
            )
            .values(is_active=False)
        )
        if actor_user_id is not None:
            stmt = stmt.values(updated_by_user_id=actor_user_id)
        
        res = await self.db.execute(stmt)
        return res.rowcount or 0

    # ─────────────────────────────────────────────────────────────
    # 복구: 도메인/오브젝트 스코프 전체
    #  team_id=None 지원
    # ─────────────────────────────────────────────────────────────
    async def reactivate_by_object(
        self,
        *,
        team_id: Optional[int],
        domain: FileDomain | str,
        object_id: int,
        actor_user_id: int | None = None,
    ) -> int:
        """
        도메인 객체의 모든 파일 복구
        
        사용: Product 복구 시 연관 파일도 복구
        """
        stmt = (
            update(FileAssetModel)
            .where(
                self._team_id_condition(team_id),
                FileAssetModel.domain == domain,
                FileAssetModel.object_id == object_id,
                FileAssetModel.is_active.is_(False),
            )
            .values(is_active=True)
        )
        if actor_user_id is not None:
            stmt = stmt.values(updated_by_user_id=actor_user_id)
        
        res = await self.db.execute(stmt)
        return res.rowcount or 0
