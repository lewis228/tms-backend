# scripts/notion_design/notion_api.py
"""Notion REST API 최소 래퍼 (urllib, 추가 의존성 없음) + 블록 빌더.

토큰은 사용자가 보안 무시하고 사용 승인. 페이지 생성 + 90블록 배치 append.
"""
from __future__ import annotations
import json
import time
import urllib.request
import urllib.error

TOKEN = "ntn_q6796350542aVAn8ZhwdtMcsWJUlsJVHJiScOZNfq5Fgiq"
TMS_PAGE_ID = "35f19518144e80538a15f00074930662"
BASE = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            payload = e.read().decode()
            if e.code in (429, 502, 503) and attempt < 3:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"Notion {method} {path} -> {e.code}: {payload[:400]}")
    raise RuntimeError("unreachable")


# ── Rich text ────────────────────────────────────────────────
def _rt(content: str, *, bold=False, code=False, color=None):
    ann = {"bold": bold, "code": code}
    if color:
        ann["color"] = color
    # Notion: 한 text 객체 content ≤2000자
    return {"type": "text", "text": {"content": content[:2000]}, "annotations": ann}


def rt(*parts):
    """parts: str | (str, opts dict). 여러 조각을 한 rich_text 리스트로."""
    out = []
    for p in parts:
        if isinstance(p, tuple):
            out.append(_rt(p[0], **p[1]))
        else:
            out.append(_rt(p))
    return out


# ── 블록 빌더 ────────────────────────────────────────────────
def h1(text): return {"type": "heading_1", "heading_1": {"rich_text": rt(text)}}
def h2(text): return {"type": "heading_2", "heading_2": {"rich_text": rt(text)}}
def h3(text): return {"type": "heading_3", "heading_3": {"rich_text": rt(text)}}
def p(*parts): return {"type": "paragraph", "paragraph": {"rich_text": rt(*parts)}}
def bullet(*parts): return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt(*parts)}}
def numbered(*parts): return {"type": "numbered_list_item", "numbered_list_item": {"rich_text": rt(*parts)}}
def divider(): return {"type": "divider", "divider": {}}


def callout(text, *, emoji="💡", color="gray_background"):
    return {"type": "callout", "callout": {
        "rich_text": rt(text), "icon": {"type": "emoji", "emoji": emoji}, "color": color}}


def code(text, *, language="text"):
    if language == "text":
        language = "plain text"  # Notion enum 은 "plain text"
    return {"type": "code", "code": {"rich_text": [_rt(text)], "language": language}}


def toggle(summary, children):
    return {"type": "toggle", "toggle": {"rich_text": rt(summary), "children": children}}


def table(headers, rows):
    """headers: [str], rows: [[str]]. 셀은 단순 텍스트."""
    width = len(headers)
    def row_block(cells):
        return {"type": "table_row", "table_row": {
            "cells": [[_rt(str(c))] for c in (list(cells) + [""] * (width - len(cells)))[:width]]}}
    children = [row_block(headers)] + [row_block(r) for r in rows]
    return {"type": "table", "table": {
        "table_width": width, "has_column_header": True, "has_row_header": False,
        "children": children}}


# ── 페이지 생성 + 배치 append ────────────────────────────────
def create_page(parent_id: str, title: str, blocks: list[dict]) -> dict:
    first, rest = blocks[:90], blocks[90:]
    page = _req("POST", "/pages", {
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": first,
    })
    pid = page["id"]
    i = 0
    while i < len(rest):
        batch = rest[i:i + 90]
        _req("PATCH", f"/blocks/{pid}/children", {"children": batch})
        i += 90
        time.sleep(0.2)
    return page


def archive_children_titled(parent_id: str, prefix: str) -> int:
    """parent 의 하위 페이지 중 title 이 prefix 로 시작하는 것 archive(재실행 멱등)."""
    n = 0
    res = _req("GET", f"/blocks/{parent_id}/children?page_size=100")
    for blk in res.get("results", []):
        if blk.get("type") == "child_page":
            title = blk["child_page"]["title"]
            if title.startswith(prefix):
                _req("PATCH", f"/pages/{blk['id']}", {"archived": True})
                n += 1
    return n
