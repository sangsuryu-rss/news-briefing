# 세림전자 뉴스 브리핑 (자동 갱신형)

기존에 매일 손으로 만들던 뉴스 브리핑을 **자동으로 갱신되는 웹페이지**로 바꾼 버전입니다.
디자인은 그대로, 뉴스 카드만 `news.js`(데이터 파일)에서 자동으로 채워집니다.

```
매일 아침 (자동) → collect.py 가 네이버 뉴스 수집 → news.js 새로 생성
        ↓
index.html 이 news.js 를 읽어 카드 자동 표시  (날씨는 wttr.in 실시간)
        ↓
사람들은 링크만 열면 항상 최신
```

## 폴더 구성

| 파일 | 역할 |
|---|---|
| `index.html` | 화면 (디자인). 손댈 일 거의 없음 |
| `news.js` | 뉴스 데이터. **collect.py 가 자동 생성** |
| `collect.py` | 수집기. 네이버 뉴스 → news.js |
| `banner.json` | (선택) 상단 배너 편집용. `banner.json.example` 참고해 만들면 표시됨 |

---

## 1. 준비: 네이버 API 키 발급 (1회, 무료)

1. https://developers.naver.com/apps 접속 → **애플리케이션 등록**
2. 사용 API에서 **검색** 선택, 환경은 **PC 웹** 아무 주소나 입력
3. 발급된 **Client ID / Client Secret** 을 메모
4. 내 PC에서 테스트하려면 환경변수로 등록 (PowerShell):
   ```powershell
   setx NAVER_CLIENT_ID "발급받은_ID"
   setx NAVER_CLIENT_SECRET "발급받은_SECRET"
   ```
   (창을 새로 열어야 적용됨)

## 2. 로컬 테스트

```powershell
pip install requests
python collect.py          # news.js 새로 생성됨
```
그 뒤 같은 폴더에서 간이 서버로 확인:
```powershell
python -m http.server 8778
# 브라우저에서 http://localhost:8778 접속
```
> 주의: `index.html` 을 그냥 더블클릭하면 브라우저 보안정책 때문에 news.js 를 못 읽습니다.
> 반드시 위처럼 서버로 열거나, 아래 3번처럼 인터넷에 올려서 확인하세요.

---

## 3. 자동화 + 공유 — 방법 A) GitHub Pages (권장 · 완전 무료 · PC 안 켜도 됨)

내 PC가 꺼져 있어도 GitHub이 매일 자동으로 뉴스를 갱신해 줍니다.

1. github.com 가입 → 새 저장소(repository) 생성 (예: `news-briefing`, Public)
2. 이 폴더의 파일 전체 업로드
3. 저장소 **Settings → Secrets and variables → Actions** 에서 비밀키 2개 등록
   - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
4. 저장소에 `.github/workflows/update.yml` 파일 추가 (아래 내용):

   ```yaml
   name: update-news
   on:
     schedule:
       - cron: '0 23 * * *'   # 매일 08:00 KST (UTC 23:00)
     workflow_dispatch:        # 수동 실행 버튼
   permissions:
     contents: write
   jobs:
     build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: '3.12' }
         - run: pip install requests
         - run: python collect.py
           env:
             NAVER_CLIENT_ID: ${{ secrets.NAVER_CLIENT_ID }}
             NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
         - run: |
             git config user.name  "news-bot"
             git config user.email "bot@users.noreply.github.com"
             git add news.js
             git commit -m "update news" || echo "변경 없음"
             git push
   ```
5. **Settings → Pages** → Branch를 `main` / `/(root)` 로 지정 → 저장
6. 몇 분 뒤 `https://<내아이디>.github.io/news-briefing/` 주소가 생깁니다.
   → **이 링크만 사람들에게 공유하면 끝.** 매일 아침 자동 갱신됩니다.

## 3. 자동화 — 방법 B) 내 PC의 작업 스케줄러 (PC가 켜져 있을 때만)

인터넷 호스팅 없이 사내망/공유폴더에 올리는 경우.

1. `run.bat` 파일을 만들어 아래 저장:
   ```bat
   cd /d "%~dp0"
   python collect.py
   ```
2. Windows **작업 스케줄러** → 기본 작업 만들기 → 매일 08:00 → `run.bat` 실행 등록
3. 갱신된 폴더를 공유 위치(웹서버/공유드라이브)에 두면 됩니다.

---

## 커스터마이즈

- **뉴스 주제 변경**: `collect.py` 상단 `SECTIONS` 의 `query` 값만 바꾸면 됩니다.
- **카테고리 개수/색상/아이콘**: 같은 `SECTIONS` 에서 조정.
- **상단 배너**: `banner.json.example` 을 복사해 `banner.json` 으로 만들고 내용 수정.
  종료일(`dday.date`)이 지나면 자동으로 사라집니다. 배너가 필요 없으면 파일을 지우면 됩니다.
- **썸네일**: collect.py 가 각 기사의 대표이미지(og:image)를 자동으로 가져옵니다.
  못 가져오는 기사는 카테고리 색상 배경으로 대체됩니다.
