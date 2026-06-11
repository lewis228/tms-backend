# scripts/confluence_publish.py
"""마크다운 문서를 Confluence 페이지(storage XHTML)로 발행하는 1회용 스크립트.

사용:
  CONFLUENCE_EMAIL=... CONFLUENCE_API_TOKEN=... \
  python scripts/confluence_publish.py <md_path> <page_id> [--dry-run]

지원 마크다운 서브셋: #/##/### 헤딩, 문단, **굵게**, *기울임*, `코드`,
``` 펜스 코드블록(ASCII 다이어그램), -/숫자. 리스트, --- 수평선.
"""
from __future__ import annotations
import html
import json
import os
import re
import sys

import httpx

BASE = "https://insightlogistics.atlassian.net/wiki"


def _inline(text: str) -> str:
    """텍스트 1줄 → 인라인 storage HTML (escape 후 **bold**/`code`/*em* 치환)."""
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", out)
    return out


def md_to_storage(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # 펜스 코드블록 → code 매크로 (CDATA 그대로 — 다이어그램 보존)
        if line.startswith("```"):
            i += 1
            buf: list[str] = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # closing fence
            body = "\n".join(buf).replace("]]>", "]]]]><![CDATA[>")
            out.append(
                '<ac:structured-macro ac:name="code">'
                '<ac:parameter ac:name="language">text</ac:parameter>'
                f"<ac:plain-text-body><![CDATA[{body}]]></ac:plain-text-body>"
                "</ac:structured-macro>"
            )
            continue

        # 수평선
        if line.strip() == "---":
            out.append("<hr/>")
            i += 1
            continue

        # 헤딩
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # 불릿 리스트
        if re.match(r"^\s*-\s+", line):
            items = []
            while i < n and re.match(r"^\s*-\s+", lines[i]):
                item_text = re.sub(r"^\s*-\s+", "", lines[i])
                items.append(f"<li>{_inline(item_text)}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # 순서 리스트
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                item_text = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                items.append(f"<li>{_inline(item_text)}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # 빈 줄
        if not line.strip():
            i += 1
            continue

        # 문단(연속 줄 병합)
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,4}\s|```|\s*-\s+|\s*\d+\.\s+|---$)", lines[i]
        ):
            buf.append(lines[i])
            i += 1
        out.append(f"<p>{_inline(' '.join(s.strip() for s in buf))}</p>")

    return "".join(out)


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    md_path, page_id = sys.argv[1], sys.argv[2]
    dry = "--dry-run" in sys.argv

    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["CONFLUENCE_API_TOKEN"]
    auth = (email, token)

    md = open(md_path, encoding="utf-8").read()
    storage = md_to_storage(md)
    print(f"storage XHTML {len(storage)}자 생성")

    with httpx.Client(timeout=30) as c:
        cur = c.get(f"{BASE}/api/v2/pages/{page_id}", auth=auth)
        cur.raise_for_status()
        page = cur.json()
        ver = page["version"]["number"]
        title = page["title"]
        print(f"대상: '{title}' (id={page_id}, v{ver})")

        if dry:
            print("--dry-run: PUT 생략. 변환 미리보기 앞 600자:")
            print(storage[:600])
            return

        r = c.put(
            f"{BASE}/api/v2/pages/{page_id}",
            auth=auth,
            json={
                "id": page_id,
                "status": "current",
                "title": title,
                "body": {"representation": "storage", "value": storage},
                "version": {"number": ver + 1, "message": "요율·정산 설계 문서 자동 발행"},
            },
        )
        if r.status_code >= 400:
            print("ERROR", r.status_code, r.text[:2000])
            sys.exit(1)
        new = r.json()
        print(f"✅ 발행 완료 — v{new['version']['number']}")
        print(f"   {BASE}{new['_links']['webui']}")


if __name__ == "__main__":
    main()
