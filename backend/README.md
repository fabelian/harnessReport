# Equity Research Backend

FastAPI 기반 멀티 에이전트 주식 분석 백엔드. OpenRouter API를 통해 Gemma·GPT-OSS 모델을 호출한다.

## 로컬 실행

```bash
# 1. 가상환경
python -m venv .venv
. .venv/Scripts/activate    # Windows PowerShell: .\.venv\Scripts\Activate.ps1
# 또는 macOS/Linux: source .venv/bin/activate

# 2. 의존성 설치
pip install -e ".[dev]"

# 3. 환경변수
cp .env.example .env
# .env 열어 OPENROUTER_API_KEY 입력

# 4. 서버 실행
uvicorn app.main:app --reload --port 8000
```

확인: <http://localhost:8000/api/health>, <http://localhost:8000/docs>

## 테스트

```bash
pytest
```

## 디렉토리

```
backend/app/
├── main.py            # FastAPI 진입
├── config.py          # Settings
├── openrouter.py      # OpenRouter 클라이언트 (Phase 1)
├── routes/            # API 엔드포인트
├── agents/            # AgentRunner (Phase 2)
├── data/              # 데이터 수집 모듈 (Phase 1)
├── prompts/           # system / methodology 마크다운
├── schemas/           # pydantic 모델
├── storage/           # SQLite jobs (Phase 3)
└── utils/             # SSE·markdown·retry
```

상세 설계: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
