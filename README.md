# SK Hynix Equity Research Harness

SK하이닉스(000660)의 주식 가치를 **펀더멘털·기술적·산업·거시·시장심리** 5개 관점에서 병렬 분석하고, 사실·추정·의견이 명확히 구분되며 출처가 추적 가능한 통합 보고서를 산출하는 Claude Code 하네스입니다.

> 본 저장소의 모든 산출물은 학습·연구 목적이며, 특정 종목의 매수·매도를 권유하지 않습니다. 투자 판단과 그 결과에 대한 책임은 전적으로 투자자 본인에게 있습니다.

본 하네스는 [revfactory/samsung-report](https://github.com/revfactory/samsung-report)의 구조를 SK하이닉스 도메인으로 변형하여 재구성한 것입니다.

---

## 산출물

| 파일 | 설명 |
|------|------|
| `SK하이닉스_주식분석_보고서_{YYYYMMDD}.md` | 5개 영역을 통합한 최종 투자 보고서 |
| `_workspace/` | 영역별 분석 원본 + QA 체크리스트 (감사 추적용) |

### `_workspace/` 구조

```
_workspace/
├── 00_input/request.md             # 사용자 요청 + 파싱 결과
├── 02_fundamental_analysis.md      # 펀더멘털 (재무·밸류에이션)
├── 02_technical_analysis.md        # 기술적 (차트·모멘텀)
├── 02_industry_analysis.md         # 산업 (메모리·HBM·NAND·CIS)
├── 02_macro_analysis.md            # 거시 (환율·금리·CapEx)
├── 02_sentiment_analysis.md        # 심리 (컨센서스·수급·뉴스)
├── 99_qa_checklist.md              # 통합·QA 체크리스트
└── 99_final_report.md              # 최종 통합 보고서 (마스터본)
```

---

## 하네스 구성

Claude Code의 **에이전트 팀 + 스킬** 패턴으로 구성된 팬아웃/팬인 + 생성-검증 복합 하네스입니다.

### 팀 구성 (5 + 1)

| 팀원 | 에이전트 | 역할 |
|------|----------|------|
| fundamental | `fundamental-analyst` | 재무 추세, DRAM/NAND/Solidigm/CIS 분해, PER/PBR/EV·EBITDA, SOTP, 간이 DCF |
| technical | `technical-analyst` | 추세·이동평균·RSI·MACD·지지저항, 3시나리오 가격대 |
| industry | `industry-analyst` | 메모리 사이클, HBM 시장 점유 1위 포지션, NAND 사이클, CIS |
| macro | `macro-analyst` | 환율·금리·빅테크 CapEx·외인 흐름·SOX 상관 |
| sentiment | `sentiment-analyst` | 컨센서스 분포·수급·공매도·뉴스·SNS 시그널 |
| **reviewer** | `integrator-reviewer` | 5개 산출물 통합·교차검증·QA·최종 보고서 |

5명 애널리스트가 **병렬**로 영역별 분석을 수행하고, 가정값(환율, 메모리 ASP, HBM 매출 비중, 컨센서스 EPS 등)은 `SendMessage`로 직접 교환합니다. 의존성이 걸린 reviewer가 마지막에 통합·QA를 수행합니다.

### 워크플로우

```
[Phase 0] 컨텍스트 확인 (_workspace 존재 → 부분/전체 재실행 판정)
   ↓
[Phase 1] 분석 기준일·요청 파싱·작업 디렉토리 준비
   ↓
[Phase 2] TeamCreate(5+1) + TaskCreate(6, reviewer 의존성)
   ↓
[Phase 3] 5명 병렬 분석 — SendMessage 페어 교환
          ├─ fundamental ↔ industry   (사업부문/HBM ASP)
          ├─ fundamental ↔ sentiment  (EPS vs 컨센서스)
          ├─ technical   ↔ sentiment  (거래량/수급)
          ├─ macro       ↔ industry   (CapEx → 수요)
          ├─ macro       ↔ fundamental(환율 가정)
          └─ macro       ↔ sentiment  (외인 흐름)
   ↓
[Phase 4] reviewer 통합 — QA 8항목 + 모순 시 1회 재작업 요청
   ↓
[Phase 5] 최종 보고서 출력 + TeamDelete + 요약 보고
```

### 공통 방법론 스킬

모든 에이전트는 [`equity-research-method`](./.claude/skills/equity-research-method/) 스킬을 로드하여 다음 공통 원칙을 준수합니다.

- **사실(F) / 추정(E) / 의견(O) 3단 라벨링**
- 모든 수치에 **출처 + 시점** 표기
- 단정적 매수·매도 권유 금지 → 시나리오·범위·트리거로 제시
- 면책 조항 및 데이터 한계 부록 필수

영역별 산식·지표·인용 규칙은 `references/` 하위 6개 문서에 정의되어 있습니다 (valuation, technical, semiconductor-industry, macro, sentiment, citations-and-disclaimers).

### 실행 (트리거)

Claude Code 세션에서 다음과 같이 요청하면 `sk-hynix-stock-orchestrator` 스킬이 동작합니다.

- `SK하이닉스 주식 가치 분석해줘`
- `000660 적정주가 보고서 작성`
- `equity research SK하이닉스`

부분 재실행:

- `기술적 분석만 다시 해줘` → `_workspace/02_technical_analysis.md` 갱신 후 `99_final_report.md` 재통합

---

## 디렉토리 구조

```
.
├── README.md
├── CLAUDE.md                       # 하네스 사용 트리거 정의
├── SK하이닉스_주식분석_보고서_*.md # 출력 보고서
├── _workspace/                     # 영역별 분석 원본
├── docs/
│   └── ARCHITECTURE.md             # 웹앱 설계 문서
├── backend/                        # FastAPI + OpenRouter (in development)
├── frontend/                       # Next.js 14 (in development)
├── docker-compose.yml
└── .claude/
    ├── agents/                     # 6개 전문가 에이전트 정의
    │   ├── fundamental-analyst.md
    │   ├── technical-analyst.md
    │   ├── industry-analyst.md
    │   ├── macro-analyst.md
    │   ├── sentiment-analyst.md
    │   └── integrator-reviewer.md
    └── skills/
        ├── sk-hynix-stock-orchestrator/  # 오케스트레이션 워크플로우
        └── equity-research-method/       # 공통 분석 방법론 + references
```

---

## 웹 애플리케이션 (MVP)

OpenRouter API(Gemma 3 27B, GPT-OSS 120B)로 동일한 다관점 분석을 **웹에서** 실행할 수 있는 별도 구현입니다. Claude Code 하네스와 독립적으로 동작합니다.

- **백엔드**: FastAPI + Python 3.11~3.13 (3.14 미지원), OpenRouter 호출, asyncio 병렬 오케스트레이션, SSE 진행률 스트리밍, SQLite 영속화
- **프론트엔드**: Next.js 14 (App Router), Tailwind, react-markdown
- **MVP 범위**: 미국 주식 1종 + 펀더멘털·기술적 2개 영역 + 통합 리뷰어
- **데이터**: yfinance (가격·재무), FRED (거시, 옵션), NewsAPI/Tavily (뉴스, 옵션) — 사전 수집 후 컨텍스트 주입

### 빠른 시작 — 데모 모드 (API 키 불필요)

OpenRouter 키 없이 UI·파이프라인 전체를 검증할 수 있는 데모 모드:

```powershell
# 백엔드 (Python 3.11~3.13 필요)
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:OPENROUTER_API_KEY = "demo"     # ← 데모 모드 활성화
uvicorn app.main:app --reload --port 8000

# 프론트엔드 (별도 터미널)
cd frontend
npm install
npm run dev
```

브라우저에서 <http://localhost:3000> → `NVDA` + 날짜 → "분석 시작" → 약 1초 안에 데모 응답 기반 보고서 출력. 백엔드 API는 <http://localhost:8000/docs>.

### 실제 분석 (OpenRouter 키 필요)

```powershell
cd backend
copy .env.example .env
# .env 편집:
#   OPENROUTER_API_KEY=sk-or-v1-...
#   FRED_API_KEY=...          (선택)
#   NEWS_API_KEY=...          (선택)

# 모델 ID 확인 (Gemma 4 26B는 미존재 가능 — 카탈로그에서 정확한 ID 찾기)
python -m scripts.list_models gemma
python -m scripts.list_models gpt-oss

# 필요하면 backend/app/schemas/inputs.py의 ModelChoice enum 업데이트
uvicorn app.main:app --reload --port 8000
```

### Docker Compose

```bash
# backend/.env 작성 후
docker compose up --build
```

### 디렉토리 구조 (웹 앱 부분)

```
backend/
├── app/
│   ├── main.py                  # FastAPI 진입 + 라우터 등록 + lifespan(init_db)
│   ├── config.py                # pydantic-settings
│   ├── openrouter.py            # AsyncOpenAI + OpenRouter base_url
│   ├── openrouter_demo.py       # demo 모드 canned 응답
│   ├── orchestrator.py          # fetch → agents.gather → reviewer → SSE
│   ├── agents/                  # FundamentalAgent / TechnicalAgent / ReviewerAgent
│   ├── data/                    # yfinance / FRED / NewsAPI / Tavily
│   ├── prompts/                 # system/{role}.md + methodology/{topic}.md
│   ├── routes/                  # /api/{health,models,analyze,jobs}
│   ├── schemas/                 # inputs / outputs / events / data
│   ├── storage/                 # aiosqlite jobs
│   └── utils/                   # prompt_loader / markdown / sse
├── scripts/
│   ├── smoke.py                 # 라이브 데이터 수집 스모크
│   └── list_models.py           # OpenRouter 카탈로그 조회
└── tests/                       # pytest (모킹 기반, 네트워크 없음)

frontend/
├── app/
│   ├── page.tsx                 # 입력 폼 + 진행률 + 보고서
│   └── analyze/[jobId]/page.tsx # 과거 작업 결과 뷰어
├── components/                  # InputForm / AgentCard / ProgressTracker / ReportViewer
└── lib/                         # types / sse / api / state(reducer)
```

### SSE 이벤트 시퀀스

```
job_start → data_fetch_start → data_fetch_done →
agent_start × 2 → agent_done × 2 (완료 순서) →
reviewer_start → reviewer_done → done (ok=true/false)
```

실패 시에도 항상 `done` 이벤트로 닫혀 프론트엔드가 클린하게 종료 가능. 부분 실패(한 에이전트 실패) 시 다른 에이전트와 reviewer는 계속 진행.

### 테스트

```powershell
cd backend
pytest                            # 단위·통합 테스트 (네트워크 없음, 모킹 기반)
python -m scripts.smoke NVDA 2026-05-13   # 라이브 yfinance + FRED + News 스모크
```

### 트러블슈팅

| 증상 | 원인·해결 |
|------|---------|
| `RuntimeError: Cannot install on Python version 3.14.x` | numba (선택적 dep)가 3.14 미지원. 본 프로젝트는 pandas-ta를 제거했으므로 영향 없음 — 캐시 정리 후 재시도 |
| `OPENROUTER_API_KEY missing` | `backend/.env`에 키 입력. 또는 `OPENROUTER_API_KEY=demo`로 데모 모드 |
| 분석 시 `JSON 검증 실패 → 재시도` 로그 | 약한 모델의 JSON 출력 실패 — 1회 자동 재시도 (`agents/base.py`). 2회 모두 실패 시 `AgentExecutionError` |
| yfinance가 빈 결과 반환 | 휴장일·잘못된 티커. `data_caveats`에 명시되어 보고서에 노출됨 |
| 모델 ID 오류 (`model not found`) | `python -m scripts.list_models gemma`로 실제 ID 확인 후 `app/schemas/inputs.py:ModelChoice` 갱신 |
| 프론트엔드 `/api/*` 502/404 | `next.config.mjs` rewrites가 `NEXT_PUBLIC_BACKEND_URL`(default `http://localhost:8000`)로 프록시 — 백엔드 미실행 또는 다른 포트 |

상세 설계·작업 분할: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)

---

## 가드레일

- 단정적 매수/매도 추천 금지 — 시나리오·범위·트리거로만 제시
- 임의 추정 금지 — 모든 수치는 출처를 갖거나 `확인 필요`로 명시
- 실시간 데이터 미확보 시 마지막 확인 가능 공식 자료 기준으로 작성하고 데이터 시점 부록 강화
- 최종 보고서에 면책 + 데이터 한계 부록 필수

---

## 라이선스 / 면책

본 저장소는 개인 학습·연구 목적의 산출물이며 어떠한 종목의 매수·매도도 권유하지 않습니다. 보고서에 포함된 수치·전망·의견은 작성 시점 기준 공개 자료에 기반하며 사후 변경될 수 있습니다.
