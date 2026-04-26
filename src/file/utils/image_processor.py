# src/file/image_processor.py
"""
이미지 자동 리사이즈 처리

조건부 리사이즈:
- 용량 > 2MB OR 해상도 > 2000px → 자동 리사이즈
- 그 외 → 원본 유지 (불필요한 처리 없음)

사용법:
    processor = ImageProcessor()
    result = processor.process_if_needed(image_bytes, filename)
    
    if result.was_processed:
        # 리사이즈된 이미지 사용
        save(result.data, result.filename)
    else:
        # 원본 사용
        save(original_bytes, original_filename)
"""
from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from typing import Optional, Tuple
import logging

from file.const.validation import (
    ALLOWED_IMAGE_EXTENSIONS,
    IMAGE_AUTO_RESIZE_THRESHOLD_SIZE,
    IMAGE_AUTO_RESIZE_THRESHOLD_PIXELS,
    IMAGE_TARGET_MAX_PIXELS,
    IMAGE_TARGET_QUALITY,
    THUMBNAIL_SIZE,
    THUMBNAIL_QUALITY,
    get_extension,
    is_image_extension,
)

logger = logging.getLogger(__name__)

# Pillow import (선택적 의존성)
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow not installed. Image processing disabled.")


@dataclass
class ProcessedImage:
    """이미지 처리 결과"""
    data: bytes              # 이미지 바이트 데이터
    filename: str            # 파일명 (리사이즈 시 확장자가 .jpg로 변경될 수 있음)
    mime: str                # MIME 타입
    size: int                # 바이트 크기
    width: int               # 가로 픽셀
    height: int              # 세로 픽셀
    was_processed: bool      # 리사이즈 처리 여부 (False면 원본 그대로)


class ImageProcessor:
    """
    이미지 자동 리사이즈 처리기
    
    정책:
    - 용량 > 2MB 이거나 해상도 > 2000px인 경우에만 리사이즈
    - 작은 이미지는 원본 그대로 유지 (불필요한 처리 방지)
    - 리사이즈 시 JPEG로 변환 (용량 효율)
    - GIF 애니메이션은 원본 유지
    """
    
    def __init__(
        self,
        threshold_size: int = IMAGE_AUTO_RESIZE_THRESHOLD_SIZE,
        threshold_pixels: int = IMAGE_AUTO_RESIZE_THRESHOLD_PIXELS,
        target_max_pixels: int = IMAGE_TARGET_MAX_PIXELS,
        target_quality: int = IMAGE_TARGET_QUALITY,
    ):
        self.threshold_size = threshold_size
        self.threshold_pixels = threshold_pixels
        self.target_max_pixels = target_max_pixels
        self.target_quality = target_quality
    
    def process_if_needed(
        self,
        image_bytes: bytes,
        filename: str,
    ) -> ProcessedImage:
        """
        필요한 경우에만 이미지 리사이즈
        
        Args:
            image_bytes: 원본 이미지 바이트
            filename: 원본 파일명
        
        Returns:
            ProcessedImage: 처리 결과 (was_processed로 처리 여부 확인)
        """
        # 이미지가 아니면 원본 반환
        if not is_image_extension(filename):
            return self._make_unprocessed_result(image_bytes, filename)
        
        # Pillow 없으면 원본 반환
        if not PILLOW_AVAILABLE:
            return self._make_unprocessed_result(image_bytes, filename)
        
        size = len(image_bytes)
        
        # 이미지 열기
        try:
            img = Image.open(BytesIO(image_bytes))
            width, height = img.size
        except Exception as e:
            logger.warning(f"Failed to open image {filename}: {e}")
            return self._make_unprocessed_result(image_bytes, filename)
        
        # GIF 애니메이션은 원본 유지 (프레임 손실 방지)
        ext = get_extension(filename)
        if ext == "gif" and getattr(img, "is_animated", False):
            logger.info(f"Skipping animated GIF: {filename}")
            return self._make_unprocessed_result(
                image_bytes, filename, width=width, height=height
            )
        
        # 리사이즈 필요 여부 판단
        needs_resize = (
            size > self.threshold_size or
            width > self.threshold_pixels or
            height > self.threshold_pixels
        )
        
        if not needs_resize:
            # 작은 이미지는 원본 그대로
            logger.debug(
                f"Image within limits, keeping original: {filename} "
                f"({size} bytes, {width}x{height})"
            )
            return self._make_unprocessed_result(
                image_bytes, filename, width=width, height=height
            )
        
        # 리사이즈 수행
        logger.info(
            f"Resizing image: {filename} "
            f"({size} bytes, {width}x{height}) -> max {self.target_max_pixels}px"
        )
        
        return self._resize_image(img, filename)
    
    def _resize_image(self, img: "Image.Image", original_filename: str) -> ProcessedImage:
        """
        실제 리사이즈 수행
        
        - 비율 유지하며 최대 픽셀로 축소
        - RGBA/P 모드는 RGB로 변환 (JPEG 저장용)
        - JPEG 품질 85%로 압축
        """
        width, height = img.size
        
        # 비율 유지하며 리사이즈
        img.thumbnail(
            (self.target_max_pixels, self.target_max_pixels),
            Image.LANCZOS
        )
        new_width, new_height = img.size
        
        # RGBA/P → RGB 변환 (JPEG 저장용)
        if img.mode in ("RGBA", "P", "LA"):
            # 투명 배경을 흰색으로
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        
        # JPEG로 압축
        output = BytesIO()
        img.save(output, format="JPEG", quality=self.target_quality, optimize=True)
        result_bytes = output.getvalue()
        
        # 파일명 확장자를 .jpg로 변경
        stem = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename
        new_filename = f"{stem}.jpg"
        
        logger.info(
            f"Resized: {original_filename} ({width}x{height}) -> "
            f"{new_filename} ({new_width}x{new_height}, {len(result_bytes)} bytes)"
        )
        
        return ProcessedImage(
            data=result_bytes,
            filename=new_filename,
            mime="image/jpeg",
            size=len(result_bytes),
            width=new_width,
            height=new_height,
            was_processed=True,
        )
    
    def create_thumbnail(
        self,
        image_bytes: bytes,
        filename: str,
        size: int = THUMBNAIL_SIZE,
        quality: int = THUMBNAIL_QUALITY,
    ) -> Optional[ProcessedImage]:
        """
        썸네일 생성 (선택적 기능)
        
        Args:
            image_bytes: 원본 이미지 바이트
            filename: 원본 파일명
            size: 썸네일 최대 픽셀
            quality: JPEG 품질
        
        Returns:
            ProcessedImage 또는 None (실패 시)
        """
        if not PILLOW_AVAILABLE:
            return None
        
        if not is_image_extension(filename):
            return None
        
        try:
            img = Image.open(BytesIO(image_bytes))
            
            # 비율 유지하며 축소
            img.thumbnail((size, size), Image.LANCZOS)
            width, height = img.size
            
            # RGB 변환
            if img.mode in ("RGBA", "P", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            # JPEG로 압축
            output = BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            result_bytes = output.getvalue()
            
            # 썸네일 파일명
            stem = filename.rsplit(".", 1)[0] if "." in filename else filename
            thumb_filename = f"{stem}_thumb.jpg"
            
            return ProcessedImage(
                data=result_bytes,
                filename=thumb_filename,
                mime="image/jpeg",
                size=len(result_bytes),
                width=width,
                height=height,
                was_processed=True,
            )
        
        except Exception as e:
            logger.warning(f"Failed to create thumbnail for {filename}: {e}")
            return None
    
    def _make_unprocessed_result(
        self,
        data: bytes,
        filename: str,
        width: int = 0,
        height: int = 0,
    ) -> ProcessedImage:
        """원본 그대로 반환할 때 사용"""
        ext = get_extension(filename)
        mime_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        
        return ProcessedImage(
            data=data,
            filename=filename,
            mime=mime,
            size=len(data),
            width=width,
            height=height,
            was_processed=False,
        )


# 싱글톤 인스턴스
image_processor = ImageProcessor()


def process_image_if_needed(image_bytes: bytes, filename: str) -> ProcessedImage:
    """
    편의 함수: 필요 시 이미지 리사이즈
    
    사용:
        from file.image_processor import process_image_if_needed
        result = process_image_if_needed(data, filename)
    """
    return image_processor.process_if_needed(image_bytes, filename)