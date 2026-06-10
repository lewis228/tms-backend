# src/leg_layer/const/status.py
"""Leg Add-on 은 더 이상 하드코딩 enum 을 쓰지 않는다.

부가요금 '타입'은 `addon` 마스터(테이블)로 통합 — 사용자 CRUD + 시스템 시드.
leg_addon 은 addon_id(FK) + code 스냅샷으로 어떤 타입을 붙였는지 가리킨다.
(옛 LegAddonCode 의 기본 코드들은 addon seed-defaults 로 이전.)
"""
from __future__ import annotations
