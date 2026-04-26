# src/file/const/validation.py
"""
파일 업로드 검증 상수 및 유틸리티

확장자, 크기, 개수 등 파일 업로드 제한 정의
"""
from __future__ import annotations
from typing import Set, Dict

# ═══════════════════════════════════════════════════════════════
# 허용 확장자 (화이트리스트)
# ═══════════════════════════════════════════════════════════════

ALLOWED_IMAGE_EXTENSIONS: Set[str] = {
    "jpg", "jpeg", "png", "gif", "webp", "bmp"
}

ALLOWED_DOCUMENT_EXTENSIONS: Set[str] = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "csv", "hwp", "hwpx"
}

ALLOWED_ARCHIVE_EXTENSIONS: Set[str] = {
    "zip", "rar", "7z", "tar", "gz"
}

# 전체 허용 확장자
ALLOWED_EXTENSIONS: Set[str] = (
    ALLOWED_IMAGE_EXTENSIONS | 
    ALLOWED_DOCUMENT_EXTENSIONS | 
    ALLOWED_ARCHIVE_EXTENSIONS
)

# ═══════════════════════════════════════════════════════════════
# 파일 크기 제한 (bytes) - 업로드 허용 최대치
# ═══════════════════════════════════════════════════════════════

MAX_UPLOAD_SIZE_IMAGE: int = 50 * 1024 * 1024       # 50MB (이미지는 리사이즈되므로 넉넉하게)
MAX_UPLOAD_SIZE_DOCUMENT: int = 50 * 1024 * 1024    # 50MB
MAX_UPLOAD_SIZE_ARCHIVE: int = 100 * 1024 * 1024    # 100MB
MAX_UPLOAD_SIZE_DEFAULT: int = 50 * 1024 * 1024     # 50MB (기타)

# ═══════════════════════════════════════════════════════════════
# 이미지 자동 리사이즈 임계값
# ═══════════════════════════════════════════════════════════════

IMAGE_AUTO_RESIZE_THRESHOLD_SIZE: int = 0   # 0 = 모든 이미지 압축 (GIF 제외, 프론트와 동기화)
IMAGE_AUTO_RESIZE_THRESHOLD_PIXELS: int = 2000            # 2000px 초과 시 리사이즈

IMAGE_TARGET_MAX_PIXELS: int = 2000     # 리사이즈 목표 최대 픽셀
IMAGE_TARGET_QUALITY: int = 85          # JPEG 압축 품질 (1-100)

# 썸네일 설정
THUMBNAIL_SIZE: int = 300               # 썸네일 최대 픽셀
THUMBNAIL_QUALITY: int = 80             # 썸네일 압축 품질

# ═══════════════════════════════════════════════════════════════
# 업로드 개수 제한
# ═══════════════════════════════════════════════════════════════

MAX_FILES_PER_REQUEST: int = 10      # 한 번에 업로드 가능한 파일 수
MAX_FILES_PER_OBJECT: int = 20       # 한 객체(제품 등)에 첨부 가능한 최대 파일 수

# ═══════════════════════════════════════════════════════════════
# MIME 타입 매핑
# ═══════════════════════════════════════════════════════════════

EXTENSION_TO_MIME: Dict[str, str] = {
    # 이미지
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    
    # 문서
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "csv": "text/csv",
    "hwp": "application/x-hwp",
    "hwpx": "application/vnd.hancom.hwpx",
    
    # 압축
    "zip": "application/zip",
    "rar": "application/x-rar-compressed",
    "7z": "application/x-7z-compressed",
    "tar": "application/x-tar",
    "gz": "application/gzip",
}

# ═══════════════════════════════════════════════════════════════
# 파일명 제한
# ═══════════════════════════════════════════════════════════════

MAX_FILENAME_LENGTH: int = 255
MIN_FILENAME_LENGTH: int = 1

# 파일명에서 금지된 문자
FORBIDDEN_FILENAME_CHARS: Set[str] = {
    "/", "\\", ":", "*", "?", '"', "<", ">", "|", "\0"
}

# ═══════════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════════

def get_extension(filename: str) -> str:
    """파일명에서 확장자 추출 (소문자)"""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def is_image_extension(filename: str) -> bool:
    """이미지 파일인지 확인"""
    ext = get_extension(filename)
    return ext in ALLOWED_IMAGE_EXTENSIONS


def is_allowed_extension(filename: str) -> bool:
    """허용된 확장자인지 확인"""
    ext = get_extension(filename)
    return ext in ALLOWED_EXTENSIONS


def get_max_upload_size(filename: str) -> int:
    """파일에 대한 최대 업로드 크기 반환"""
    ext = get_extension(filename)
    
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return MAX_UPLOAD_SIZE_IMAGE
    elif ext in ALLOWED_DOCUMENT_EXTENSIONS:
        return MAX_UPLOAD_SIZE_DOCUMENT
    elif ext in ALLOWED_ARCHIVE_EXTENSIONS:
        return MAX_UPLOAD_SIZE_ARCHIVE
    else:
        return MAX_UPLOAD_SIZE_DEFAULT


def get_mime_type(filename: str) -> str:
    """파일명에서 MIME 타입 추론"""
    ext = get_extension(filename)
    return EXTENSION_TO_MIME.get(ext, "application/octet-stream")


def is_valid_filename(filename: str) -> bool:
    """파일명 유효성 검사"""
    if not filename:
        return False
    
    if len(filename) < MIN_FILENAME_LENGTH or len(filename) > MAX_FILENAME_LENGTH:
        return False
    
    for char in FORBIDDEN_FILENAME_CHARS:
        if char in filename:
            return False
    
    return True


def format_file_size(size_bytes: int) -> str:
    """바이트를 읽기 쉬운 형식으로 변환"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"