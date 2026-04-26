"""
로그 필터: /health, /metrics 등 소음 라인 제외
- 표준 logging Handler에 filter로 장착
"""

class HealthCheckFilter:
    def filter(self, record):
        msg = getattr(record, "msg", "")
        # msg가 문자열로 들어오는 표준 logging 라인에서만 동작
        if not isinstance(msg, str):
            return True
        noisy = ("/health" in msg) or ("/metrics" in msg)
        return not noisy
