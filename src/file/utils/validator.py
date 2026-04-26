# src/file/validator.py
"""
파일 업로드 검증 로직

upload-urls 요청 시 파일명 유효성 검사
"""
from __future__ import annotations
from typing import List

from common.exceptions import BadRequestException
from file.const.validation import (
    ALLOWED_EXTENSIONS,
    MAX_FILES_PER_REQUEST,
    MAX_FILENAME_LENGTH,
    FORBIDDEN_FILENAME_CHARS,
    get_extension,
    is_allowed_extension,
)


class FileUploadValidator:
    """
    파일 업로드 검증기
    
    사용:
        validator = FileUploadValidator()
        validator.validate_filenames(filenames)
    """
    
    def validate_filenames(self, filenames: List[str]) -> None:
        """
        파일명 목록 검증 (upload-urls 요청 시)
        
        Args:
            filenames: 업로드 요청 파일명 목록
        
        Raises:
            BadRequestException: 검증 실패 시
        """
        # 빈 요청 체크
        if not filenames:
            raise BadRequestException("업로드할 파일이 없습니다.")
        
        # 한 번에 업로드 개수 체크
        if len(filenames) > MAX_FILES_PER_REQUEST:
            raise BadRequestException(
                f"한 번에 최대 {MAX_FILES_PER_REQUEST}개까지 업로드 가능합니다. "
                f"(요청: {len(filenames)}개)"
            )
        
        # 개별 파일명 검증
        for filename in filenames:
            self._validate_single_filename(filename)
    
    def _validate_single_filename(self, filename: str) -> None:
        """
        단일 파일명 검증
        
        Args:
            filename: 파일명
        
        Raises:
            BadRequestException: 검증 실패 시
        """
        # 1. 파일명 유효성
        if not filename:
            raise BadRequestException("파일명이 비어있습니다.")
        
        if len(filename) > MAX_FILENAME_LENGTH:
            raise BadRequestException(
                f"파일명이 너무 깁니다. (최대 {MAX_FILENAME_LENGTH}자)"
            )
        
        # 2. 금지 문자 체크
        for char in FORBIDDEN_FILENAME_CHARS:
            if char in filename:
                raise BadRequestException(
                    f"파일명에 사용할 수 없는 문자가 포함되어 있습니다: {repr(char)}"
                )
        
        # 3. 확장자 체크
        ext = get_extension(filename)
        
        if not ext:
            raise BadRequestException(f"파일 확장자가 없습니다: {filename}")
        
        if not is_allowed_extension(filename):
            allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise BadRequestException(
                f"허용되지 않는 파일 형식입니다: .{ext}\n"
                f"허용 형식: {allowed_list}"
            )


# 싱글톤 인스턴스
file_validator = FileUploadValidator()


def validate_filenames(filenames: List[str]) -> None:
    """
    편의 함수: 파일명 목록 검증
    
    사용:
        from file.validator import validate_filenames
        validate_filenames(request.filenames)
    """
    file_validator.validate_filenames(filenames)