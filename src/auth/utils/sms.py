# src/auth/utils/sms.py
"""SMS 발송 — 데모용 Mock (콘솔 출력).

실제 운영 시 Twilio / Aligo / NHN Cloud 같은 게이트웨이로 교체.
환경변수 SMS_PROVIDER=mock|twilio|aligo 로 분기 가능 (현재는 mock 만).
"""
from __future__ import annotations
import structlog

logger = structlog.get_logger(__name__)


def send_otp_sms(*, phone: str, code: str, app_name: str = "TMS") -> None:
    """OTP SMS 발송. 데모는 콘솔 출력 + log.

    실제 호출:
        text = f"[{app_name}] 인증번호: {code}"
        twilio_client.messages.create(to=phone, body=text)
    """
    text = f"[{app_name}] 인증번호 [{code}] 를 입력해주세요. 3분 이내 유효."
    logger.info("sms_otp_send", phone=phone, code=code)
    # 콘솔에도 명시적으로 출력 (데모 시연 시 터미널에서 확인 가능)
    print("\n" + "═" * 60)
    print(f"📱 SMS → {phone}")
    print(f"   {text}")
    print("═" * 60 + "\n")


def normalize_phone(phone: str) -> str:
    """입력된 폰번호를 정규화. '010-1234-5678' / '01012345678' / '+82-10-1234-5678' 모두 지원.

    리턴: 숫자만 (예: "01012345678"). DB 저장 / 조회 표준.
    """
    digits = "".join(c for c in phone if c.isdigit())
    # +82 → 0 변환 (대한민국 전제)
    if digits.startswith("82") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits
