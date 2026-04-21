# 개인 가계부 (Personal Finance Tracker)

토스 앱의 거래내역을 자동으로 수집·분류해 SQLite에 저장하고, Streamlit 대시보드로 시각화하는 개인용 가계부.

## 구성

```
Toss (Playwright) → 분류(YAML 규칙) → SQLite → Streamlit 대시보드
                                              ↑
                              n8n 스케줄러 → webhook_server.py (매일 09:00 자동 동기화)
```

## 사전 요구사항

| 항목 | 버전 | 비고 |
|------|------|------|
| Python | 3.9+ | [python.org](https://python.org) |
| Docker Desktop | 최신 | n8n 자동화용 |
| OS | macOS / Windows 10·11 / Linux | |

## 빠른 시작

### 1. 저장소 복제

```bash
git clone <repo-url>
cd personal_finance
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 토스 계정 정보 입력:

```env
TOSS_PHONE=010-1234-5678
TOSS_PASSWORD=your_password
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=strong_password_here
```

파일 권한 제한:
```bash
# macOS / Linux
chmod 600 .env

# Windows
icacls .env /inheritance:r /grant:r "%USERNAME%:F"
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. 최초 로그인 (브라우저 세션 저장)

```bash
python run.py --login
```

브라우저가 열리면 토스 앱 OTP 인증을 완료하세요. 세션이 `data/toss_session.json`에 저장됩니다.

### 5. 동기화 테스트

```bash
python run.py --days 7
```

### 6. 대시보드 실행

```bash
# 가상환경 활성화 후 실행
source .venv/bin/activate
streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

브라우저에서 http://127.0.0.1:8501 접속.

**macOS 빠른 실행:** `start_dashboard.command` 파일을 더블클릭하거나 Dock에 등록하면 클릭 한 번으로 실행됩니다.

```bash
# 또는 alias 등록 후 터미널에서
echo 'alias finance="~/dev/personal_finance/start_dashboard.command"' >> ~/.zshrc
source ~/.zshrc
finance
```

## 자동 동기화 설정 (n8n)

매일 아침 자동으로 거래내역을 수집하려면 n8n을 설정합니다.

### 1. n8n 시작

```bash
docker-compose up -d
```

### 2. n8n 접속 및 비밀번호 변경

http://127.0.0.1:5678 → `admin / (설정한 비밀번호)` → Settings → Change Password

### 3. webhook 서버 시작

```bash
# 기본 (로컬 전용, 권장)
python webhook_server.py

# Docker(n8n)에서 호출 가능하도록 (host.docker.internal 사용 시)
WEBHOOK_HOST=0.0.0.0 python webhook_server.py
```

### 4. 워크플로우 가져오기

n8n UI → Workflows → Import → `docs/n8n/workflow.json` 파일 선택 → Save & Activate

> 워크플로우를 수정했다면 내보내서 `docs/n8n/workflow.json`을 덮어쓰고 커밋하세요.

## 주요 명령어

```bash
# 전체 테스트
pytest -v

# 단일 파일 테스트
pytest tests/test_database.py -v

# 최초 로그인 (브라우저 OTP)
python run.py --login

# 거래내역 수집 (최근 N일)
python run.py --days 7

# 드라이런 (DB 저장 없이 미리보기)
python run.py --dry-run

# 대시보드
streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501

# webhook 서버 (n8n 연동)
python webhook_server.py

# n8n
docker-compose up -d
docker-compose down
```

## 디렉터리 구조

```
personal_finance/
├── crawler/
│   ├── base.py          # BaseCrawler (컨텍스트 매니저)
│   └── toss.py          # Playwright 기반 토스 크롤러
├── db/
│   └── database.py      # SQLite 레이어 (중복 제거, crawl_log)
├── parser/
│   └── categorizer.py   # YAML 규칙 기반 카테고리 분류
├── dashboard/
│   └── app.py           # Streamlit 대시보드 (홈/거래내역/차트/설정)
├── config/
│   └── categories.yaml  # 카테고리 키워드 규칙 (직접 편집)
├── docs/
│   └── n8n/
│       └── workflow.json  # n8n 워크플로우 (import/export)
├── tests/               # pytest 테스트
├── data/                # 세션 파일, SQLite DB (gitignore)
├── logs/                # 크롤 로그 (gitignore)
├── run.py               # 크롤 진입점 (exit: 0=성공, 1=오류, 2=인증실패)
├── webhook_server.py    # HTTP 서버 127.0.0.1:9000 (n8n → run.py)
├── docker-compose.yml   # n8n 컨테이너
└── .env                 # 토스 계정 정보 (gitignore, 직접 생성)
```

## 카테고리 커스터마이징

`config/categories.yaml` 파일을 직접 편집합니다:

```yaml
rules:
  - match: ["스타벅스", "커피빈"]
    category: 식비
  - match: ["넷플릭스"]
    category: 구독/OTT
default_category: "미분류"
```

변경 후 다음 동기화부터 적용됩니다. 기존 거래내역은 대시보드 → 거래내역 → 카테고리 수정에서 변경 가능합니다.

## 새 데이터 소스 추가

`crawler/naver_pay.py` 형태로 `BaseCrawler`를 상속해 구현:

```python
from crawler.base import BaseCrawler

class NaverPayCrawler(BaseCrawler):
    def login(self): ...
    def fetch_transactions(self, start, end): ...
    def logout(self): ...
```

## 보안 참고사항

- `data/`, `logs/`, `.env`, `n8n_data/` → gitignore (절대 커밋 금지)
- 모든 로컬 서버는 `127.0.0.1` 전용 (포트 8501, 9000, 5678)
- `WEBHOOK_HOST=0.0.0.0` 설정 시 Windows 방화벽에서 포트 9000 외부 차단 확인
- `data/toss_session.json`에 로그인 세션 토큰이 저장됨 → 파일 권한 제한 권장

## 문제 해결

**`docker-compose up -d` 실패**
→ Docker Desktop이 실행 중인지 확인 (시스템 트레이 고래 아이콘)

**n8n HTTP Request 오류 (`host.docker.internal:9000`)**
→ `WEBHOOK_HOST=0.0.0.0 python webhook_server.py`로 실행

**토스 로그인 실패**
→ `python run.py --login`으로 세션 재발급

**카테고리가 적용 안 됨**
→ `config/categories.yaml` 편집 후 재동기화 (`python run.py --days 30`)
