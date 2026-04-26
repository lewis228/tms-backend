# src/file/service.py
"""
MinIO 기반 파일 서비스

주요 변경점:
- 로컬 파일시스템 → MinIO 오브젝트 스토리지
- 직접 HMAC 서명 → MinIO SDK presigned URL
- 서버 경유 업로드 → Presigned URL로 클라이언트 직접 업로드
- Nginx X-Accel-Redirect → 불필요 (MinIO가 직접 서빙)

🆕 추가된 기능:
- 파일명 검증 (확장자 화이트리스트, 개수 제한)
- 이미지 자동 리사이즈 (조건부: 2MB 초과 또는 2000px 초과 시)
- 파일 복사 (제품 복제용)
- OAuth 프로필 이미지 저장 (외부 URL → MinIO)

⚠️ 트랜잭션 안전성 (중요!):
- DB 작업을 먼저 수행하고, MinIO 삭제는 flush() 성공 후에 수행
- 이렇게 해야 DB 롤백 시 MinIO 파일이 남아있어 404 방지
- MinIO 삭제 실패 시 고아 파일만 남음 (새벽 정리 스케줄러로 처리)

 tenant_id=None 지원:
- User 도메인은 팀과 무관하므로 tenant_id=None
- 경로: private/{domain}/{object_id}/... (tenant- prefix 없음)

워크플로우:
1. 클라이언트가 업로드 URL 요청 → FastAPI가 presigned PUT URL 발급 (+ 검증)
2. 클라이언트가 MinIO에 직접 업로드 (서버 부하 없음!)
3. 업로드 완료 후 commit 요청 → 이미지 리사이즈 → tmp → 영구 경로로 복사 + DB 메타 저장
4. 다운로드 시 presigned GET URL 발급 → 클라이언트가 MinIO에서 직접 다운로드
"""
from __future__ import annotations
import secrets
import mimetypes
import logging
from typing import Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from botocore.exceptions import ClientError

from common.pagination.schemas.pagination_response import CursorPaginationResult
from file.const.consts import (
    get_s3_client,
    MINIO_BUCKET,
    PRESIGNED_UPLOAD_TTL,
    PRESIGNED_DOWNLOAD_TTL,
    ObjectKeyBuilder,
    temp_key,
    rewrite_presigned_url,
    public_direct_url,
)
from file.const.domains import FileDomain
from file.const.validation import is_image_extension
from file.model import FileAssetModel
from file.repository import FileRepository
from file.schemas.request import PaginateFileListRequestSchema
from file.schemas.response import FileInfoResponseSchema
from file.utils.validator import validate_filenames
from file.utils.image_processor import process_image_if_needed, ProcessedImage

logger = logging.getLogger(__name__)


class FileService:
    """
    MinIO 기반 파일 처리 서비스

    정책 요약:
    - presigned URL로 업로드/다운로드 (서버 부하 최소화)
    - temp 업로드 → commit으로 영구 저장 (2단계 워크플로우 유지)
    - DB 메타 관리는 기존과 동일
    - 파일 삭제는 DB 메타 삭제 + MinIO 오브젝트 삭제
    
    🆕 추가:
    - upload-urls: 파일명 검증 (확장자, 개수)
    - commit: 이미지 자동 리사이즈 (조건부)
    - copy_files: 기존 파일 복사 (제품 복제용)
    - save_oauth_profile_image: OAuth 프로필 이미지 저장
    
     tenant_id=None 지원:
    - User 도메인은 tenant_id=None으로 처리
    - 경로에서 tenant- prefix 생략
    
    ⚠️ 트랜잭션 안전성:
    - DB 작업 먼저, MinIO 삭제는 flush() 성공 후
    - 롤백 시 MinIO 파일 유지 → 404 방지
    """

    def __init__(self, db: AsyncSession | None):
        self.db = db
        self.repo = FileRepository(db) if db else None
        self.s3 = get_s3_client()
        self.bucket = MINIO_BUCKET

    # ─────────────────────────────────────────────────────────────
    # ▼ URL 주입 헬퍼 (공통 사용)
    # ─────────────────────────────────────────────────────────────
    def inject_file_urls(self, files: List[Any]) -> None:
        """
        파일 리스트의 url 필드에 presigned URL 주입
        
        사용 예시:
            response = ProductDetailResponseSchema.model_validate(row)
            self.file_svc.inject_file_urls(response.files)
        
        Args:
            files: FileNestedSchema 또는 url/logical_path 속성을 가진 객체 리스트
        """
        for f in files:
            if hasattr(f, 'logical_path') and f.logical_path:
                f.url = self.generate_download_url(f.logical_path)

    def inject_product_file_urls(self, product: Any) -> None:
        """
        Product 중첩 스키마의 files에 presigned URL 주입

        사용 예시:
            product_nested = ProductNestedSchema.model_validate(ln.product)
            self.file_svc.inject_product_file_urls(product_nested)

        Args:
            product: ProductNestedSchema 또는 files 속성을 가진 객체
        """
        if product and hasattr(product, 'files') and product.files:
            self.inject_file_urls(product.files)

    def inject_product_line_file_urls(self, product: Any) -> None:
        """
        ProductLineNestedSchema의 files + bundle_components[].component_product.files에 URL 주입.
        """
        if not product:
            return
        if hasattr(product, 'files') and product.files:
            self.inject_file_urls(product.files)
        if hasattr(product, 'bundle_components') and product.bundle_components:
            for comp in product.bundle_components:
                cp = getattr(comp, 'component_product', None)
                if cp and hasattr(cp, 'files') and cp.files:
                    self.inject_file_urls(cp.files)

    # ─────────────────────────────────────────────────────────────
    # ▼ 커서 페이지네이션 (기존과 동일)
    # ─────────────────────────────────────────────────────────────
    async def list_paginated(
        self, *, tenant_id: int, request: PaginateFileListRequestSchema
    ) -> CursorPaginationResult[FileInfoResponseSchema]:
        assert self.repo, "This method requires DB session"
        page = await self.repo.list_files_paginated(tenant_id=tenant_id, request=request)
        items = [FileInfoResponseSchema.model_validate(x) for x in page.data]
        return CursorPaginationResult[FileInfoResponseSchema](meta=page.meta, data=items)

    # ─────────────────────────────────────────────────────────────
    # ▼ 1) Presigned Upload URL 발급 (🆕 검증 추가)
    # ─────────────────────────────────────────────────────────────
    def generate_upload_urls(
        self, filenames: list[str], *, ttl: Optional[int] = None
    ) -> tuple[str, list[dict]]:
        """
        임시 업로드용 presigned PUT URL 발급

        🆕 검증 추가:
        - 파일명 유효성 (금지 문자, 길이)
        - 확장자 화이트리스트
        - 업로드 개수 제한 (최대 10개)

        Args:
            filenames: 업로드할 파일명 목록
            ttl: URL 유효시간 (초), 기본값 PRESIGNED_UPLOAD_TTL

        Returns:
            (token, [{"filename": "...", "upload_url": "...", "key": "..."}, ...])
            - token: 나중에 commit 시 사용
            - upload_url: 클라이언트가 PUT 요청할 URL
            - key: MinIO 오브젝트 키
        
        Raises:
            BadRequestException: 파일명 검증 실패 시
        """
        # 🆕 파일명 검증
        validate_filenames(filenames)
        
        token = secrets.token_urlsafe(16)
        expires_in = ttl or PRESIGNED_UPLOAD_TTL
        results = []

        for filename in filenames:
            key = temp_key(token, filename)
            
            # Content-Type 추론
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "application/octet-stream"

            # Presigned PUT URL 생성
            url = self.s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )

            results.append({
                "filename": filename,
                "upload_url": rewrite_presigned_url(url),
                "key": key,
                "content_type": content_type,
            })

        return token, results

    # ─────────────────────────────────────────────────────────────
    # ▼ 2) 커밋 (트랜잭션 안전 버전) - 방법 2: 개별 키 처리
    # ─────────────────────────────────────────────────────────────
    async def commit(
        self,
        *,
        tenant_id: Optional[int],  #  None 허용 (User 도메인용)
        domain: FileDomain,
        object_id: int,
        subdir: Optional[str],
        add_temp_keys: list[str],  # 🆕 토큰 대신 개별 키 (예: "tmp/token1/a.jpg")
        remove_file_ids: list[int],
        actor_user_id: Optional[int],
        is_public: bool = False,
    ) -> list[FileAssetModel]:
        """
        임시 업로드 파일을 영구 저장소로 커밋 (트랜잭션 안전)

         방법 2: 개별 키 처리
        - 기존: 토큰 폴더 스캔 → 폴더 내 모든 파일 커밋
        - 변경: 개별 키 직접 처리 → 프론트에서 선택한 파일만 커밋

         tenant_id=None 지원:
        - User 도메인은 tenant_id=None으로 처리
        - 경로: private/{domain}/{object_id}/...

        ⚠️ 트랜잭션 안전성:
        - DB 작업(삭제, 저장)을 먼저 수행
        - flush() 성공 후에만 MinIO 삭제 수행
        - DB 롤백 시 MinIO 파일 유지 → 404 방지

        처리 순서:
        1. [DB] 기존 file_asset 조회 → 삭제할 경로 저장
        2. [DB] 기존 file_asset 레코드 삭제
        3. [MinIO 읽기] temp 파일 읽기 + 이미지 처리
        4. [MinIO 쓰기] 영구 경로에 저장
        5. [DB] 새 file_asset 레코드 저장
        6. [DB] flush() - 여기까지 실패하면 롤백
        ─────────────────────────────────────────
        7. [MinIO] 기존 파일 삭제 (DB 성공 후!)
        8. [MinIO] temp 파일 삭제
        """
        assert self.repo, "This method requires DB session"

        # MinIO 삭제 작업을 나중에 수행하기 위한 경로 저장
        paths_to_delete: list[str] = []
        temp_paths_to_delete: list[str] = []

        # ─────────────────────────────────────────────────────────
        # 1. [DB] 기존 파일 조회 → 삭제할 경로 저장
        # ─────────────────────────────────────────────────────────
        if remove_file_ids:
            files_to_remove = await self.repo.select_by_ids(
                tenant_id=tenant_id,  #  None 가능
                ids=remove_file_ids
            )
            paths_to_delete = [f.logical_path for f in files_to_remove]

            # ─────────────────────────────────────────────────────
            # 2. [DB] 기존 file_asset 레코드 삭제 (MinIO 삭제 전!)
            # ─────────────────────────────────────────────────────
            await self.repo.delete_files_by_ids(
                tenant_id=tenant_id,  #  None 가능
                ids=remove_file_ids
            )

        # ─────────────────────────────────────────────────────────
        # 3-5. 새 파일 처리 (temp → 영구) - 개별 키 직접 처리
        # ─────────────────────────────────────────────────────────
        key_builder = ObjectKeyBuilder(
            tenant_id=tenant_id,  #  None 가능
            domain=domain,
            object_id=object_id,
            subdir=subdir or "",
            is_public=is_public,
        )

        new_assets: list[FileAssetModel] = []

        # 🆕 개별 키 직접 처리 (토큰 폴더 스캔 대신)
        for src_key in add_temp_keys:
            # 키에서 파일명 추출 (예: "tmp/token1/a.jpg" → "a.jpg")
            filename = src_key.split("/")[-1]

            # MinIO에서 파일 정보 조회
            try:
                head_response = self.s3.head_object(Bucket=self.bucket, Key=src_key)
                size = head_response.get("ContentLength", 0)
            except ClientError:
                # 파일이 없으면 건너뜀 (이미 삭제되었거나 잘못된 키)
                logger.warning(f"Temp file not found: {src_key}")
                continue

            # 이미지인 경우 리사이즈 처리
            if is_image_extension(filename):
                asset = await self._process_and_save_image(
                    src_key=src_key,
                    original_filename=filename,
                    original_size=size,
                    key_builder=key_builder,
                    tenant_id=tenant_id,
                    domain=domain,
                    object_id=object_id,
                    subdir=subdir or "",
                    is_public=is_public,
                    actor_user_id=actor_user_id,
                )
            else:
                # 이미지가 아닌 파일은 기존 로직대로 복사
                asset = await self._copy_and_save_file(
                    src_key=src_key,
                    filename=filename,
                    size=size,
                    key_builder=key_builder,
                    tenant_id=tenant_id,
                    domain=domain,
                    object_id=object_id,
                    subdir=subdir or "",
                    is_public=is_public,
                    actor_user_id=actor_user_id,
                )

            if asset:
                new_assets.append(asset)
                # temp 경로 저장 (나중에 삭제)
                temp_paths_to_delete.append(src_key)

        # ─────────────────────────────────────────────────────────
        # 5. [DB] 새 file_asset 레코드 저장
        # ─────────────────────────────────────────────────────────
        saved = await self.repo.add_files(new_assets)

        # ─────────────────────────────────────────────────────────
        # 6. [DB] flush() - 여기까지 실패하면 전체 롤백
        # ─────────────────────────────────────────────────────────
        await self.db.flush()

        # ═════════════════════════════════════════════════════════
        # 이 시점부터는 DB 작업 성공 확정
        # MinIO 작업 실패해도 DB는 이미 성공 상태
        # ═════════════════════════════════════════════════════════

        # ─────────────────────────────────────────────────────────
        # 7. [MinIO] 기존 파일 삭제 (DB 성공 후!)
        # ─────────────────────────────────────────────────────────
        for path in paths_to_delete:
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=path)
            except ClientError:
                pass  # 실패해도 OK (고아 파일은 새벽에 정리)

        # ─────────────────────────────────────────────────────────
        # 8. [MinIO] temp 파일 삭제
        # ─────────────────────────────────────────────────────────
        for path in temp_paths_to_delete:
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=path)
            except ClientError:
                pass  # 실패해도 OK (새벽에 정리)

        return saved

    # ─────────────────────────────────────────────────────────────
    # ▼ 3) 파일 복사 (제품 복제용) 🆕
    # ─────────────────────────────────────────────────────────────
    async def copy_files(
        self,
        *,
        tenant_id: int,
        source_file_ids: list[int],
        target_domain: FileDomain,
        target_object_id: int,
        target_subdir: str,
        actor_user_id: Optional[int],
        is_public: bool = False,
    ) -> list[FileAssetModel]:
        """
        기존 파일들을 새 오브젝트로 복사 (제품 복제용)
        
        사용 예시:
            # 제품 복제 시 기존 이미지 복사
            await self.file_svc.copy_files(
                tenant_id=self.tenant_id,
                source_file_ids=[1, 2, 3],
                target_domain=FileDomain.PRODUCT,
                target_object_id=new_product.id,
                target_subdir="images",
                actor_user_id=user_id,
            )
        
        처리 순서:
        1. 소스 파일 정보 조회
        2. MinIO에서 파일 복사
        3. 새 DB 레코드 생성
        4. flush()
        
        Args:
            tenant_id: 팀 ID
            source_file_ids: 복사할 원본 파일 ID 목록
            target_domain: 대상 도메인 (예: FileDomain.PRODUCT)
            target_object_id: 대상 오브젝트 ID (예: 새 제품 ID)
            target_subdir: 하위 디렉토리 (예: "images")
            actor_user_id: 작업자 ID
            is_public: 공개 여부
        
        Returns:
            생성된 FileAssetModel 목록
        """
        if not source_file_ids:
            return []
        
        assert self.repo, "This method requires DB session"
        
        # ─────────────────────────────────────────────────────────
        # 1. 소스 파일 정보 조회
        # ─────────────────────────────────────────────────────────
        source_files = await self.repo.select_by_ids(tenant_id=tenant_id, ids=source_file_ids)
        if not source_files:
            return []
        
        # ─────────────────────────────────────────────────────────
        # 2. 대상 키 빌더 생성
        # ─────────────────────────────────────────────────────────
        key_builder = ObjectKeyBuilder(
            tenant_id=tenant_id,
            domain=target_domain,
            object_id=target_object_id,
            subdir=target_subdir,
            is_public=is_public,
        )
        
        new_assets: list[FileAssetModel] = []
        
        for source_file in source_files:
            # 원본 파일 정보
            src_key = source_file.logical_path
            filename = source_file.filename
            
            # 목적지 키 생성
            dst_key = key_builder.key(filename)
            
            # 이름 충돌 시 suffix 추가
            if self._object_exists(dst_key):
                stem, ext = self._split_filename(filename)
                filename = f"{stem}-{secrets.token_hex(4)}{ext}"
                dst_key = key_builder.key(filename)
            
            # ─────────────────────────────────────────────────────
            # 3. MinIO에서 파일 복사
            # ─────────────────────────────────────────────────────
            try:
                self.s3.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": src_key},
                    Key=dst_key,
                )
            except ClientError as e:
                logger.error(f"Failed to copy file in MinIO: {src_key} -> {dst_key}, {e}")
                continue
            
            # ─────────────────────────────────────────────────────
            # 4. 새 DB 메타 생성
            # ─────────────────────────────────────────────────────
            new_asset = FileAssetModel(
                tenant_id=tenant_id,
                domain=target_domain,
                object_id=target_object_id,
                subdir=target_subdir,
                filename=filename,
                size=source_file.size,
                mime=source_file.mime,
                is_public=is_public,
                logical_path=dst_key,
                created_by_user_id=actor_user_id,
            )
            new_assets.append(new_asset)
        
        # ─────────────────────────────────────────────────────────
        # 5. DB에 저장 + flush
        # ─────────────────────────────────────────────────────────
        if new_assets:
            saved = await self.repo.add_files(new_assets)
            await self.db.flush()
            return saved
        
        return []

    # ─────────────────────────────────────────────────────────────
    # ▼ 4) OAuth 프로필 이미지 저장 🆕
    # ─────────────────────────────────────────────────────────────
    async def save_oauth_profile_image(
        self,
        *,
        user_id: int,
        image_url: str,
    ) -> Optional[FileAssetModel]:
        """
        OAuth 프로필 이미지 저장 (외부 URL → MinIO)
        
        Google, Kakao, Apple 등 OAuth 회원가입 시 프로필 이미지를 저장합니다.
        외부 URL에서 이미지를 다운로드하여 리사이즈 후 MinIO에 저장합니다.
        
        경로: private/user/{user_id}/profile/avatar.jpg
        
        Args:
            user_id: 사용자 ID
            image_url: OAuth provider가 제공한 프로필 이미지 URL
        
        Returns:
            저장된 FileAssetModel 또는 None (실패 시)
        
        Note:
            - 이미지 다운로드 실패 시 warning 로그만 남기고 None 반환
            - 회원가입 트랜잭션에는 영향 없음 (이미지는 나중에 업로드 가능)
        """
        if not image_url:
            return None
        
        import httpx
        
        # ─────────────────────────────────────────────────────────
        # 1. 외부 URL에서 이미지 다운로드 (메모리에 저장)
        # ─────────────────────────────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(image_url)
                if response.status_code != 200:
                    logger.warning(f"Failed to download OAuth profile image: {image_url}, status={response.status_code}")
                    return None
                image_bytes = response.content
        except Exception as e:
            logger.warning(f"Failed to download OAuth profile image: {image_url}, error={e}")
            return None
        
        # ─────────────────────────────────────────────────────────
        # 2. 이미지 처리 (필요 시 리사이즈)
        # ─────────────────────────────────────────────────────────
        result: ProcessedImage = process_image_if_needed(image_bytes, "avatar.jpg")
        
        # ─────────────────────────────────────────────────────────
        # 3. MinIO 경로 생성 (User는 tenant_id=None)
        # ─────────────────────────────────────────────────────────
        key_builder = ObjectKeyBuilder(
            tenant_id=None,  # User는 플랫폼 전역
            domain=FileDomain.USER,
            object_id=user_id,
            subdir="profile",
            is_public=False,
        )
        dst_key = key_builder.key(result.filename)
        
        # 이름 충돌 시 suffix 추가
        if self._object_exists(dst_key):
            stem = result.filename.rsplit(".", 1)[0] if "." in result.filename else result.filename
            ext = f".{result.filename.rsplit('.', 1)[1]}" if "." in result.filename else ""
            new_filename = f"{stem}-{secrets.token_hex(4)}{ext}"
            dst_key = key_builder.key(new_filename)
            result = ProcessedImage(
                data=result.data,
                filename=new_filename,
                mime=result.mime,
                size=result.size,
                width=result.width,
                height=result.height,
                was_processed=result.was_processed,
            )
        
        # ─────────────────────────────────────────────────────────
        # 4. MinIO에 업로드
        # ─────────────────────────────────────────────────────────
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=dst_key,
                Body=result.data,
                ContentType=result.mime,
            )
            logger.info(f"OAuth profile image saved: user_id={user_id}, path={dst_key}")
        except ClientError as e:
            logger.error(f"Failed to upload OAuth profile image to MinIO: {dst_key}, error={e}")
            return None
        
        # ─────────────────────────────────────────────────────────
        # 5. DB 메타 생성 + 저장
        # ─────────────────────────────────────────────────────────
        asset = FileAssetModel(
            tenant_id=None,  # User는 플랫폼 전역
            domain=FileDomain.USER,
            object_id=user_id,
            subdir="profile",
            filename=result.filename,
            size=result.size,
            mime=result.mime,
            is_public=False,
            logical_path=dst_key,
            created_by_user_id=user_id,
        )
        
        if self.repo:
            saved = await self.repo.add_files([asset])
            await self.db.flush()
            return saved[0] if saved else None
        
        return None

    async def _process_and_save_image(
        self,
        *,
        src_key: str,
        original_filename: str,
        original_size: int,
        key_builder: ObjectKeyBuilder,
        tenant_id: Optional[int],  #  None 가능
        domain: FileDomain,
        object_id: int,
        subdir: str,
        is_public: bool,
        actor_user_id: Optional[int],
    ) -> Optional[FileAssetModel]:
        """
        🆕 이미지 처리 후 저장
        
        - 조건에 따라 리사이즈 또는 원본 유지
        - MinIO에 저장
        - FileAssetModel 반환
        """
        try:
            # MinIO에서 이미지 다운로드
            response = self.s3.get_object(Bucket=self.bucket, Key=src_key)
            image_bytes = response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to download image from MinIO: {src_key}, {e}")
            return None
        
        # 이미지 처리 (필요 시 리사이즈)
        result: ProcessedImage = process_image_if_needed(image_bytes, original_filename)
        
        # 최종 파일명과 데이터
        final_filename = result.filename
        final_data = result.data
        final_size = result.size
        final_mime = result.mime
        
        if result.was_processed:
            logger.info(
                f"Image resized: {original_filename} ({original_size} bytes) -> "
                f"{final_filename} ({final_size} bytes)"
            )
        
        # 목적지 키 생성
        dst_key = key_builder.key(final_filename)
        
        # 이름 충돌 시 suffix 추가
        if self._object_exists(dst_key):
            stem = final_filename.rsplit(".", 1)[0] if "." in final_filename else final_filename
            ext = f".{final_filename.rsplit('.', 1)[1]}" if "." in final_filename else ""
            final_filename = f"{stem}-{secrets.token_hex(4)}{ext}"
            dst_key = key_builder.key(final_filename)
        
        # MinIO에 업로드
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=dst_key,
                Body=final_data,
                ContentType=final_mime,
            )
        except ClientError as e:
            logger.error(f"Failed to upload processed image to MinIO: {dst_key}, {e}")
            return None
        
        # DB 메타 생성
        return FileAssetModel(
            tenant_id=tenant_id,  #  None 가능
            domain=domain,
            object_id=object_id,
            subdir=subdir,
            filename=final_filename,
            size=final_size,
            mime=final_mime,
            is_public=is_public,
            logical_path=dst_key,
            created_by_user_id=actor_user_id,
        )

    async def _copy_and_save_file(
        self,
        *,
        src_key: str,
        filename: str,
        size: int,
        key_builder: ObjectKeyBuilder,
        tenant_id: Optional[int],  #  None 가능
        domain: FileDomain,
        object_id: int,
        subdir: str,
        is_public: bool,
        actor_user_id: Optional[int],
    ) -> Optional[FileAssetModel]:
        """
        이미지가 아닌 파일 복사 (기존 로직)
        """
        # 목적지 키 생성
        dst_key = key_builder.key(filename)
        
        # 이름 충돌 시 suffix 추가
        if self._object_exists(dst_key):
            stem, ext = self._split_filename(filename)
            filename = f"{stem}-{secrets.token_hex(4)}{ext}"
            dst_key = key_builder.key(filename)
        
        # MinIO 내부 복사 (같은 버킷)
        try:
            self.s3.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": src_key},
                Key=dst_key,
            )
        except ClientError as e:
            logger.error(f"Failed to copy file in MinIO: {src_key} -> {dst_key}, {e}")
            return None
        
        # MIME 타입 추론
        mime, _ = mimetypes.guess_type(filename)
        
        # DB 메타 생성
        return FileAssetModel(
            tenant_id=tenant_id,  #  None 가능
            domain=domain,
            object_id=object_id,
            subdir=subdir,
            filename=filename,
            size=size,
            mime=mime or "application/octet-stream",
            is_public=is_public,
            logical_path=dst_key,
            created_by_user_id=actor_user_id,
        )

    # ─────────────────────────────────────────────────────────────
    # ▼ 5) Presigned Download URL 발급
    # ─────────────────────────────────────────────────────────────
    def generate_download_url(
        self, logical_path: str, *, ttl: Optional[int] = None
    ) -> str:
        """
        다운로드 URL 발급

        - public/ 파일: 직접 URL (서명 없음, 만료 없음)
        - private/ 파일: presigned URL (서명 있음, 만료 있음)

        Args:
            logical_path: DB에 저장된 오브젝트 키 (예: "private/tenant-7/product/123/images/a.jpg")
            ttl: URL 유효시간 (초) — private 파일에만 적용

        Returns:
            MinIO URL (MINIO_PUBLIC_URL 설정 시 외부 URL로 변환)
        """
        if logical_path.startswith("public/"):
            return public_direct_url(logical_path)

        expires_in = ttl or PRESIGNED_DOWNLOAD_TTL

        url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": logical_path},
            ExpiresIn=expires_in,
        )
        return rewrite_presigned_url(url)

    # ─────────────────────────────────────────────────────────────
    # ▼ 6) 파일 삭제 (DB + MinIO) - 단독 사용 시
    # ─────────────────────────────────────────────────────────────
    async def _remove_files(
        self, *, 
        tenant_id: Optional[int],  #  None 가능
        file_ids: list[int]
    ) -> None:
        """
        파일 삭제: DB 메타 삭제 + MinIO 오브젝트 삭제 (트랜잭션 안전)
        
        ⚠️ 주의: commit() 내부에서는 이 메서드를 사용하지 않음
        commit()은 자체적으로 트랜잭션 안전한 순서로 처리
        
        이 메서드는 단독으로 파일만 삭제할 때 사용
        """
        if not file_ids:
            return
        assert self.repo, "This method requires DB session"

        # 1. 삭제 대상 조회 (logical_path 필요)
        files = await self.repo.select_by_ids(tenant_id=tenant_id, ids=file_ids)
        paths_to_delete = [f.logical_path for f in files]

        # 2. [DB] 메타 삭제 먼저
        await self.repo.delete_files_by_ids(tenant_id=tenant_id, ids=file_ids)
        
        # 3. [DB] flush()
        await self.db.flush()

        # 4. [MinIO] 오브젝트 삭제 (DB 성공 후!)
        for path in paths_to_delete:
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=path)
            except ClientError:
                pass  # 실패해도 OK (고아 파일은 새벽에 정리)

    # ─────────────────────────────────────────────────────────────
    # ▼ 7) 리스트 (기존과 동일)
    # ─────────────────────────────────────────────────────────────
    async def list(
        self, *, tenant_id: int, domain: str, object_id: int, subdir: Optional[str]
    ) -> list[FileAssetModel]:
        assert self.repo, "This method requires DB session"
        return await self.repo.list_files(
            tenant_id=tenant_id, domain=domain, object_id=object_id, subdir=subdir
        )

    # ─────────────────────────────────────────────────────────────
    # ▼ 8) 스코프 삭제 (도메인 객체 전체) - 트랜잭션 안전 버전
    # ─────────────────────────────────────────────────────────────
    async def delete_scope(
        self, *, 
        tenant_id: Optional[int],  #  None 가능
        domain: str, 
        object_id: int
    ) -> int:
        """
        도메인 객체 스코프 전체 삭제 (DB + MinIO) - 트랜잭션 안전
        
         tenant_id=None 지원:
        - User 도메인 삭제 시 tenant_id=None으로 호출
        
        순서:
        1. [DB] 파일 조회 → 경로 저장
        2. [DB] 레코드 삭제
        3. [DB] flush()
        4. [MinIO] 파일 삭제 (DB 성공 후!)
        """
        assert self.repo, "This method requires DB session"

        # 1. 삭제 대상 조회
        files = await self.repo.list_files(
            tenant_id=tenant_id, domain=domain, object_id=object_id, subdir=None
        )
        
        if not files:
            return 0
        
        paths_to_delete = [f.logical_path for f in files]

        # 2. [DB] 메타 삭제
        deleted_rows = await self.repo.delete_scope(
            tenant_id=tenant_id, domain=domain, object_id=object_id
        )
        
        # 3. [DB] flush()
        await self.db.flush()

        # 4. [MinIO] 오브젝트 삭제 (DB 성공 후!)
        for path in paths_to_delete:
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=path)
            except ClientError:
                pass  # 실패해도 OK

        return deleted_rows

    # ─────────────────────────────────────────────────────────────
    # ▼ 9) 팀 전체 삭제 (팀 퍼지 시)
    # ─────────────────────────────────────────────────────────────
    async def delete_tenant_files(self, tenant_id: int) -> None:
        """
        팀 퍼지 시 해당 팀의 모든 파일 삭제

        MinIO에서는 prefix로 일괄 삭제 가능
        """
        # public/tenant-{id}/ 와 private/tenant-{id}/ 모두 삭제
        for visibility in ["public", "private"]:
            prefix = f"{visibility}/tenant-{tenant_id}/"
            self._delete_prefix(prefix)

    def _delete_prefix(self, prefix: str) -> None:
        """
        특정 prefix 아래의 모든 오브젝트 삭제
        """
        paginator = self.s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            contents = page.get("Contents", [])
            if not contents:
                continue

            # 한번에 1000개까지 삭제 가능
            objects = [{"Key": obj["Key"]} for obj in contents]
            self.s3.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": objects},
            )

    # ─────────────────────────────────────────────────────────────
    # ▼ 10) 소프트 삭제 (DB만, MinIO 유지)
    # ─────────────────────────────────────────────────────────────
    async def soft_deactivate_by_object(
        self,
        *,
        tenant_id: Optional[int],
        domain: FileDomain | str,
        object_id: int,
        actor_user_id: int | None = None,
    ) -> int:
        """
        도메인 객체의 모든 파일 소프트삭제 (DB만, MinIO 유지)
        
        사용: Product 소프트삭제 시 연관 파일도 소프트삭제
        - 복구 가능하도록 MinIO 파일은 그대로 유지
        
        Args:
            tenant_id: 팀 ID (User는 None)
            domain: 파일 도메인 (예: FileDomain.PRODUCT)
            object_id: 대상 오브젝트 ID
            actor_user_id: 작업자 ID
        
        Returns:
            소프트삭제된 파일 수
        """
        assert self.repo, "This method requires DB session"
        return await self.repo.soft_deactivate_by_object(
            tenant_id=tenant_id,
            domain=domain,
            object_id=object_id,
            actor_user_id=actor_user_id,
        )

    # ─────────────────────────────────────────────────────────────
    # ▼ 11) 복구 (DB만)
    # ─────────────────────────────────────────────────────────────
    async def reactivate_by_object(
        self,
        *,
        tenant_id: Optional[int],
        domain: FileDomain | str,
        object_id: int,
        actor_user_id: int | None = None,
    ) -> int:
        """
        도메인 객체의 모든 파일 복구
        
        사용: Product 복구 시 연관 파일도 복구
        - MinIO 파일은 소프트삭제 시 유지했으므로 그대로 있음
        
        Args:
            tenant_id: 팀 ID (User는 None)
            domain: 파일 도메인 (예: FileDomain.PRODUCT)
            object_id: 대상 오브젝트 ID
            actor_user_id: 작업자 ID
        
        Returns:
            복구된 파일 수
        """
        assert self.repo, "This method requires DB session"
        return await self.repo.reactivate_by_object(
            tenant_id=tenant_id,
            domain=domain,
            object_id=object_id,
            actor_user_id=actor_user_id,
        )

    # ─────────────────────────────────────────────────────────────
    # ▼ 유틸리티
    # ─────────────────────────────────────────────────────────────
    def _object_exists(self, key: str) -> bool:
        """오브젝트 존재 여부 확인"""
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    @staticmethod
    def _split_filename(filename: str) -> tuple[str, str]:
        """파일명을 stem과 extension으로 분리"""
        if "." in filename:
            parts = filename.rsplit(".", 1)
            return parts[0], f".{parts[1]}"
        return filename, ""