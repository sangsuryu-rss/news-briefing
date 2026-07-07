# -*- coding: utf-8 -*-
"""
세림전자 뉴스 브리핑 - 자동 수집기
------------------------------------------------
네이버 뉴스 검색 API에서 카테고리별 최신 기사를 수집해
같은 폴더의 news.js 를 새로 만든다. (index.html 이 이 파일을 읽어 화면 표시)

실행:  python collect.py
필요:  네이버 개발자센터(https://developers.naver.com) 에서 발급받은 키를
       환경변수로 등록
         NAVER_CLIENT_ID     = 발급받은 Client ID
         NAVER_CLIENT_SECRET = 발급받은 Client Secret
자동화: GitHub Actions 또는 Windows 작업 스케줄러로 매일 아침 1회 실행 (README 참조)
"""

import os
import re
import sys
import json
import html
import datetime
from urllib.parse import quote, urljoin

import requests

# ─────────────────────────────────────────────────────────────
# 1) 수집할 카테고리 정의  (title/색상/아이콘은 index.html 디자인과 1:1 대응)
#    query 만 바꾸면 원하는 주제로 얼마든지 커스터마이즈 가능
# ─────────────────────────────────────────────────────────────
# sort: "sim"=정확도순(주제 적합·잡음 적음) / "date"=최신순
#   실적발표일 등엔 최신순이 특정 이슈로 도배되므로, 주제형 섹션은 sim 권장
SECTIONS = [
    {"cls": "",        "icon": "📺", "title": "삼성전자 가전",     "color": "#1428a0", "query": "삼성전자 비스포크 가전", "sort": "sim",  "count": 4},
    {"cls": "ai",      "icon": "🤖", "title": "AI 동향",           "color": "#00a86b", "query": "AI 기술 도입 활용",     "sort": "date", "count": 4},
    {"cls": "partner", "icon": "🤝", "title": "삼성 협력사 동향",  "color": "#7b3fe4", "query": "삼성전자 협력사 부품",   "sort": "sim",  "count": 4},
    {"cls": "harness", "icon": "🔌", "title": "와이어하네스·전장", "color": "#e8842c", "query": "와이어링 하네스 전장",   "sort": "date", "count": 4},
]

# 언론사 도메인 → 한글 표기 (없으면 도메인 그대로)
SRC_MAP = {
    "etnews.com": "전자신문", "donga.com": "동아일보", "it.donga.com": "IT동아",
    "chosun.com": "조선일보", "joongang.co.kr": "중앙일보", "mt.co.kr": "머니투데이",
    "dt.co.kr": "디지털타임스", "inews24.com": "아이뉴스24", "mk.co.kr": "매일경제",
    "mbn.co.kr": "MBN", "sedaily.com": "서울경제", "hankyung.com": "한국경제",
    "businesspost.co.kr": "비즈니스포스트", "bntnews.co.kr": "BNT뉴스",
    "newsinside.kr": "뉴스인사이드", "pinpointnews.co.kr": "핀포인트뉴스",
    "theguru.co.kr": "더구루", "newspim.com": "뉴스핌", "dailian.co.kr": "데일리안",
    "seoul.co.kr": "서울신문", "ajunews.com": "아주경제", "edaily.co.kr": "이데일리",
    "thebell.co.kr": "더벨", "techm.kr": "테크M", "asiatime.co.kr": "아시아타임즈",
    "greened.kr": "그린포스트", "hankookilbo.com": "한국일보", "businessplus.kr": "비즈니스플러스",
    "sentv.co.kr": "서울경제TV", "youthdaily.co.kr": "유스경제", "gokorea.kr": "고코리아",
    "theviewers.co.kr": "더뷰어스", "tf.co.kr": "더팩트",
    "ddaily.co.kr": "디지털데일리", "aitimes.kr": "AI타임스", "aitimes.com": "AI타임스",
    "eroun.net": "이로운넷", "consumernews.co.kr": "소비자가만드는신문",
    "industrynews.co.kr": "인더스트리뉴스", "hansbiz.co.kr": "한스경제",
    "seouleconews.com": "서울경제뉴스", "ddaily.com": "디지털데일리",
    "hani.co.kr": "한겨레", "etoday.co.kr": "이투데이", "cnbnews.com": "CNB뉴스",
    "seoultimes.news": "서울타임즈", "yonhapnewstv.co.kr": "연합뉴스TV",
    "ktnews.com": "전자신문", "zdnet.co.kr": "ZDNet코리아", "yna.co.kr": "연합뉴스",
    "news1.kr": "뉴스1", "newsis.com": "뉴시스", "fnnews.com": "파이낸셜뉴스",
    "ddaily.kr": "디지털데일리",
}

CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_JS = os.path.join(HERE, "news.js")
BANNER_JSON = os.path.join(HERE, "banner.json")  # (선택) 상단 배너 편집용


def clean(text: str) -> str:
    """네이버가 넣어주는 <b> 태그와 HTML 엔티티 제거."""
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def source_of(link: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)/", link + "/")
    host = m.group(1) if m else ""
    for dom, name in SRC_MAP.items():
        if host.endswith(dom):
            return name
    return host.split(".")[0] if host else "뉴스"


def fmt_date(pub: str) -> str:
    """'Tue, 07 Jul 2026 10:39:00 +0900' → '07/07'"""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pub).strftime("%m/%d")
    except Exception:
        return datetime.datetime.now().strftime("%m/%d")


def og_image(url: str) -> str:
    """기사 페이지에서 대표 이미지(og:image)를 추출. 실패 시 빈 문자열."""
    try:
        r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0 (news-briefing-bot)"})
        r.raise_for_status()
        html_text = r.text[:200000]  # 앞부분만 (og:image 는 <head> 안에 있음)
        for pat in (
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ):
            m = re.search(pat, html_text, re.I)
            if m:
                img = html.unescape(m.group(1))
                if img.startswith("//"):
                    return "https:" + img
                if img.startswith("/"):            # 루트 상대경로 → 절대경로 보정
                    return urljoin(url, img)
                return img
    except Exception:
        pass
    return ""


def search_news(query: str, count: int, sort: str = "date"):
    """네이버 뉴스 검색. 결과가 count 개가 될 때까지 유효 기사 수집."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("환경변수 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 설정되지 않았습니다.")
    url = "https://openapi.naver.com/v1/search/news.json?query=%s&display=%d&sort=%s" % (quote(query), count + 4, sort)
    r = requests.get(url, timeout=8, headers={
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    })
    r.raise_for_status()
    items = []
    for it in r.json().get("items", []):
        link = it.get("link") or it.get("originallink") or ""
        art_url = it.get("originallink") or link  # og:image 는 원문에서 더 잘 잡힘
        items.append({
            "title": clean(it.get("title")),
            "desc": clean(it.get("description")),
            "src": source_of(art_url),
            "date": fmt_date(it.get("pubDate", "")),
            "url": link,
            "img": og_image(art_url),
        })
        if len(items) >= count:
            break
    return items


def load_banner():
    """banner.json 이 있으면 그 내용을, 없으면 배너 미표시."""
    if os.path.exists(BANNER_JSON):
        try:
            with open(BANNER_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("[경고] banner.json 읽기 실패:", e)
    return {"show": False}


def main():
    try:                                   # GitHub 서버는 UTC → 한국시간(KST)으로 표기
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    except Exception:
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    weekday = "월화수목금토일"[now.weekday()]
    updated = now.strftime("%Y.%m.%d (") + weekday + now.strftime(") %H:%M")

    sections, all_items = [], []
    for sec in SECTIONS:
        try:
            items = search_news(sec["query"], sec["count"], sec.get("sort", "date"))
            print("[수집] %-14s %d건" % (sec["title"], len(items)))
        except Exception as e:
            print("[실패] %-14s %s" % (sec["title"], e))
            items = []
        sections.append({k: sec[k] for k in ("cls", "icon", "title", "color")} | {"items": items})
        all_items += items

    # 오늘의 주요 뉴스: 이미지가 있는 기사 우선으로 상위 6건
    ranked = sorted(all_items, key=lambda x: 0 if x["img"] else 1)[:6]
    ranking = [{"title": it["title"], "url": it["url"], "img": it["img"]} for it in ranked]

    data = {"updatedAt": updated, "banner": load_banner(), "sections": sections, "ranking": ranking}

    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("/* collect.py 가 자동 생성 — 직접 수정하지 마세요 */\n")
        f.write("window.NEWS_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    total = sum(len(s["items"]) for s in sections)
    print("[완료] news.js 생성 · 총 %d건 · %s" % (total, updated))
    if total == 0:
        sys.exit(1)  # 스케줄러가 실패를 인지하도록


if __name__ == "__main__":
    main()
