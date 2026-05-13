# Equity Research Web App — 설계 문서

OpenRouter 기반 멀티 에이전트 주식 분석 웹 애플리케이션의 아키텍처·API·디렉토리 구조·작업 분할 명세.

## 1. 결정 사항 요약

| 항목 | 선택 | 이유 |
|------|------|------|
| 스택 | FastAPI (백엔드) + Next.js (프론트) | asyncio 병렬·데이터 수집 라이브러리 풍부, 프론트 분리로 SSE/배포 유연성 |
| 데이터 흐름 | 사전 수집 후 컨텍스트 주입 | 결정적 동작, Gemma/GPT-OSS의 tool calling 신뢰도 한계 회피 |
| MVP 범위 | 미국 주식 1종 + 펀더멘털·기술적 2개 영역 | 파이프라인·UI·OpenRouter 통합 검증에 집중, 한국·5영역은 Phase 2 |
| LLM | OpenRouter API (Gemma 3 27B, GPT-OSS 120B 사용자 선택) | 사용자 요구. openai SDK 호환 |
| 출력 형식 | JSON 스키마 강제 → 마크다운 변환 | 약한 모델에서도 파싱 가능, 검증 용이 |

> **모델 ID 검증 필요**: 사용자가 언급한 "Gemma 4 26B"는 공개 시점 기준 미존재 가능성이 있어 OpenRouter 모델 카탈로그에서 실제 ID 확인 후 `config.py`에 등록한다. 본 문서에서는 잠정 ID로 `google/gemma-3-27b-it`, `openai/gpt-oss-120b`를 가정한다.

## 2. 전체 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend — Next.js 14 (App Router)                           │
│                                                                │
│  /                     입력 폼 (asset, asOfDate, model)        │
│  /analyze/[jobId]      진행률 + 최종 보고서                    │
│                                                                │
│  components/                                                   │
│    InputForm           폼 검증, POST /api/analyze              │
│    ProgressTracker     SSE 구독, 에이전트별 카드               │
│    ReportViewer        react-markdown + remark-gfm             │
└────────────────────────┬───────────────────────────────────────┘
                         │ HTTP + SSE
┌────────────────────────▼───────────────────────────────────────┐
│  Backend — FastAPI (Python 3.11+)                              │
│                                                                │
│  POST /api/analyze     SSE 스트림 (data → agents → review)     │
│  GET  /api/jobs/{id}   완료 작업 조회 (SQLite 캐시)            │
│  GET  /api/health      헬스체크                                │
│                                                                │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ DataFetcher │→ │ Orchestrator │→ │ ReviewerAgent    │      │
│  └─────────────┘  │ (asyncio)    │  └──────────────────┘      │
│        │          └──────┬───────┘            │                │
│        │     ┌──────┴──────┐                  │                │
│        │     ▼             ▼                  │                │
│        │  ┌─────────┐  ┌─────────┐            │                │
│        │  │ Fund.   │  │ Tech.   │            │                │
│        │  │ Agent   │  │ Agent   │            │                │
│        │  └─────────┘  └─────────┘            │                │
│        │     │             │                  │                │
│        ▼     ▼             ▼                  ▼                │
│     OpenRouter API (openai SDK + base_url)                     │
└────────────────────────────────────────────────────────────────┘
        │                │                │              │
        ▼                ▼                ▼              ▼
   yfinance      SEC EDGAR / FRED   NewsAPI/Tavily   OpenRouter
```

## 3. 디렉토리 구조

```
harnessReport/
├── backend/
│   ├── app/
│   │   ├── main.py                          # FastAPI 앱 진입
│   │   ├── config.py                        # Settings (pydantic-settings)
│   │   ├── openrouter.py                    # OpenRouter 클라이언트 래퍼
│   │   │
│   │   ├── routes/
│   │   │   ├── analyze.py                   # POST /api/analyze (SSE)
│   │   │   ├── jobs.py                      # GET /api/jobs/{id}
│   │   │   └── health.py
│   │   │
│   │   ├── orchestrator.py                  # asyncio.gather + SSE 이벤트 발신
│   │   │
│   │   ├── agents/
│   │   │   ├── base.py                      # AgentRunner 추상 클래스
│   │   │   ├── fundamental.py               # FundamentalAgent
│   │   │   ├── technical.py                 # TechnicalAgent
│   │   │   └── reviewer.py                  # IntegratorReviewer
│   │   │
│   │   ├── data/
│   │   │   ├── resolver.py                  # 자산명 → 티커 정규화
│   │   │   ├── fetcher.py                   # 전체 수집 오케스트레이터
│   │   │   ├── prices.py                    # yfinance OHLCV + 지표 계산
│   │   │   ├── fundamentals.py              # SEC EDGAR + yfinance 재무
│   │   │   ├── news.py                      # NewsAPI / Tavily
│   │   │   └── macro.py                     # FRED (FED rate, 10Y, DXY)
│   │   │
│   │   ├── prompts/
│   │   │   ├── system/
│   │   │   │   ├── fundamental.md           # 펀더멘털 에이전트 system prompt
│   │   │   │   ├── technical.md             # 기술적 에이전트 system prompt
│   │   │   │   └── reviewer.md              # 통합 리뷰어 system prompt
│   │   │   └── methodology/
│   │   │       ├── valuation.md             # 기존 references/valuation.md 변환
│   │   │       ├── technical.md             # 기존 references/technical.md 변환
│   │   │       └── citations.md             # 인용·면책 표준
│   │   │
│   │   ├── schemas/
│   │   │   ├── inputs.py                    # AnalyzeRequest (asset, asOfDate, model)
│   │   │   ├── outputs.py                   # FundamentalOutput, TechnicalOutput, etc.
│   │   │   ├── events.py                    # SSE 이벤트 타입
│   │   │   └── data.py                      # 수집된 데이터 컨테이너
│   │   │
│   │   ├── storage/
│   │   │   ├── db.py                        # SQLite 연결 (aiosqlite)
│   │   │   └── jobs.py                      # job 저장·조회
│   │   │
│   │   └── utils/
│   │       ├── sse.py                       # SSE 이벤트 포맷터
│   │       ├── markdown.py                  # JSON output → 마크다운 변환
│   │       └── retry.py                     # tenacity 기반 OpenRouter 재시도
│   │
│   ├── tests/
│   │   ├── test_data_fetcher.py
│   │   ├── test_agents.py                   # mocked OpenRouter
│   │   └── test_orchestrator.py
│   │
│   ├── pyproject.toml                       # 의존성 (FastAPI, openai, yfinance, ...)
│   ├── Dockerfile
│   └── .env.example                         # OPENROUTER_API_KEY, FRED_API_KEY, ...
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                         # 입력 폼
│   │   ├── analyze/
│   │   │   └── [jobId]/
│   │   │       └── page.tsx                 # 진행률 + 결과
│   │   └── globals.css
│   │
│   ├── components/
│   │   ├── InputForm.tsx
│   │   ├── ProgressTracker.tsx              # 3개 카드 (data + 2 agents + reviewer)
│   │   ├── AgentCard.tsx                    # 단일 에이전트 상태
│   │   ├── ReportViewer.tsx                 # react-markdown
│   │   └── ui/                              # shadcn/ui 컴포넌트
│   │
│   ├── lib/
│   │   ├── api.ts                           # 백엔드 fetch 래퍼
│   │   ├── sse.ts                           # EventSource 훅
│   │   └── types.ts                         # 백엔드 schemas 미러
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.mjs
│   └── Dockerfile
│
├── docs/
│   └── ARCHITECTURE.md                      # 이 문서
│
├── docker-compose.yml                       # backend + frontend + (선택: redis)
├── .gitignore
├── CLAUDE.md
├── README.md
├── SK하이닉스_주식분석_보고서_20260513.md       # 기존 산출물
├── _workspace/                              # 기존 산출물
└── .claude/                                 # 기존 멀티 에이전트 정의 (재사용 소스)
```

## 4. API 명세

### POST `/api/analyze`
Server-Sent Events 스트림 응답.

**Request**
```json
{
  "asset": "NVDA",
  "asOfDate": "2026-05-13",
  "model": "openai/gpt-oss-120b"
}
```

**Response (SSE)**
```
event: job_start
data: {"jobId":"uuid-v4","asset":"NVDA","asOfDate":"2026-05-13"}

event: data_fetch_start
data: {"sources":["prices","fundamentals","news","macro"]}

event: data_fetch_progress
data: {"source":"prices","status":"done"}

event: data_fetch_done
data: {"summary":{"priceRows":1260,"filings":4,"newsCount":47,"macroRows":260}}

event: agent_start
data: {"agent":"fundamental"}

event: agent_start
data: {"agent":"technical"}

event: agent_done
data: {"agent":"fundamental","output":{...AgentOutput}}

event: agent_done
data: {"agent":"technical","output":{...}}

event: reviewer_start
data: {}

event: reviewer_progress
data: {"chunk":"...streaming markdown..."}

event: reviewer_done
data: {"report":"# NVDA Analysis ...","tokensUsed":12345}

event: done
data: {"jobId":"...","durationMs":42000}
```

**Error 이벤트**
```
event: error
data: {"stage":"agent","agent":"fundamental","message":"OpenRouter 429"}
```

### GET `/api/jobs/{jobId}`
```json
{
  "jobId": "uuid",
  "asset": "NVDA",
  "asOfDate": "2026-05-13",
  "model": "openai/gpt-oss-120b",
  "status": "completed|failed|running",
  "createdAt": "2026-05-13T...",
  "completedAt": "...",
  "report": "# ... markdown ...",
  "agentOutputs": { "fundamental": {...}, "technical": {...} },
  "data": { ... 수집 데이터 요약 ... },
  "tokensUsed": 12345
}
```

### GET `/api/health`
```json
{ "status": "ok", "openrouter": "ok|degraded" }
```

## 5. 데이터 스키마 (백엔드)

```python
# schemas/inputs.py
class AnalyzeRequest(BaseModel):
    asset: str = Field(min_length=1, max_length=20)         # "NVDA" 또는 "NVIDIA"
    as_of_date: date                                          # "2026-05-13"
    model: ModelChoice = ModelChoice.gpt_oss_120b

class ModelChoice(str, Enum):
    gemma_3_27b = "google/gemma-3-27b-it"
    gpt_oss_120b = "openai/gpt-oss-120b"

# schemas/data.py
class AnalysisData(BaseModel):
    asset: AssetMeta              # 티커, 회사명, 거래소, 통화, 시총
    prices: PriceSeries           # OHLCV + 지표 (MA20/50/200, RSI, MACD, BBands)
    fundamentals: Fundamentals    # 최근 4Q 손익·BS·현금흐름·핵심 비율
    news: list[NewsItem]          # 최근 90일, 상위 50개
    macro: MacroSnapshot          # FED rate, 10Y, DXY, VIX
    as_of_date: date

# schemas/outputs.py
class FundamentalOutput(BaseModel):
    summary: str                          # 3~5문장 요약
    financial_trend: list[FinancialRow]  # 분기별 매출·OP·EPS
    valuation: ValuationBlock            # PER, PBR, EV/EBITDA, peers
    scenarios: ScenarioBlock             # bull/base/bear: 가정 + 목표가 범위
    data_caveats: list[str]              # 데이터 한계
    citations: list[Citation]            # 출처 + 시점

class TechnicalOutput(BaseModel):
    summary: str
    trend: TrendBlock                    # 정/역배열, MA 위치
    momentum: MomentumBlock              # RSI, MACD, Stochastic
    support_resistance: list[Level]
    scenarios: ScenarioBlock
    data_caveats: list[str]

class ReviewerOutput(BaseModel):
    final_report_markdown: str           # 최종 통합 보고서
    discrepancies: list[Discrepancy]    # 모순 항목
    open_questions: list[str]

# schemas/events.py
class SSEEvent(BaseModel):
    event: Literal["job_start","data_fetch_start","data_fetch_progress",
                   "data_fetch_done","agent_start","agent_done",
                   "reviewer_start","reviewer_progress","reviewer_done",
                   "error","done"]
    data: dict
```

## 6. 에이전트 구현 패턴

```python
# agents/base.py
class AgentRunner(ABC):
    role: str
    output_schema: type[BaseModel]
    system_prompt_path: str
    methodology_paths: list[str]

    async def run(self, ctx: AnalysisData, model: str) -> BaseModel:
        system = self._build_system()
        user = self._build_user(ctx)
        raw = await openrouter.chat(
            model=model,
            system=system,
            user=user,
            response_format={"type": "json_schema",
                             "json_schema": self.output_schema.model_json_schema()},
        )
        return self.output_schema.model_validate_json(raw)

    def _build_system(self) -> str:
        return load(self.system_prompt_path) + "\n\n" + \
               "\n\n".join(load(p) for p in self.methodology_paths)

    def _build_user(self, ctx: AnalysisData) -> str:
        # 데이터를 LLM이 읽기 좋은 마크다운 표/JSON으로 정형화
        return render_data_for_prompt(ctx, role=self.role)
```

**중요 가드레일** (모든 에이전트 system prompt에 포함):
1. 임의 수치 생성 금지 — 컨텍스트에 없는 값은 "확인 필요"로 표기
2. 사실/추정/의견 라벨 강제 (출력 스키마에 label 필드 포함)
3. 인용은 컨텍스트의 citation 풀에서만 선택
4. JSON 스키마 위반 시 1회 재시도 (Pydantic 검증 실패 시)

## 7. 데이터 수집 명세

| 영역 | 소스 | 라이브러리/API | 키 필요 | 호출당 비용 |
|------|------|---------------|--------|-----------|
| 가격·OHLCV | Yahoo Finance | `yfinance` | 무료 | 무료 |
| 기술 지표 | 자체 계산 | `pandas-ta` | - | - |
| 분기 재무 | yfinance + SEC EDGAR | `yfinance`, `sec-edgar-api` | 무료(rate limited) | 무료 |
| 뉴스 | NewsAPI 또는 Tavily | HTTP | 유료(키 필요) | $0.001~$0.005/검색 |
| 거시 | FRED | `fredapi` | 무료(키 등록) | 무료 |
| 자산명 → 티커 | yfinance Lookup | `yfinance` | 무료 | 무료 |

**MVP 절약 옵션**: 뉴스는 NewsAPI Developer plan (무료 100req/day) 또는 RSS 스크레이프로 충분.

## 8. 작업 분할 (Implementation Tasks)

순서대로 진행 권장. 각 작업은 1~3시간 단위로 분할.

### Phase 0: 환경 셋업
- [ ] `backend/` 디렉토리 + `pyproject.toml` (FastAPI, openai, yfinance, fredapi, pydantic-settings, aiosqlite, tenacity, pytest, pytest-asyncio)
- [ ] `frontend/` 디렉토리 + Next.js 14 init (`npx create-next-app`, Tailwind, shadcn)
- [ ] `.env.example` 작성 (OPENROUTER_API_KEY, FRED_API_KEY, NEWS_API_KEY)
- [ ] `docker-compose.yml` 작성

### Phase 1: 백엔드 핵심
- [ ] `config.py`, `openrouter.py` — OpenRouter 호출 테스트 (echo prompt → 응답 출력)
- [ ] `data/prices.py` — NVDA OHLCV 1년 + MA20/50/200, RSI14, MACD 계산
- [ ] `data/fundamentals.py` — NVDA 최근 4Q 재무
- [ ] `data/news.py` — NVDA 최근 30일 뉴스 10건
- [ ] `data/macro.py` — FRED 기준금리·10Y·DXY 최근 6개월
- [ ] `data/fetcher.py` — 위 4개를 asyncio.gather로 병렬 수집, `AnalysisData` 반환

### Phase 2: 에이전트
- [ ] `prompts/system/fundamental.md` 작성 (기존 `.claude/agents/fundamental-analyst.md` 변환)
- [ ] `prompts/methodology/valuation.md` 작성 (기존 reference 변환, MVP 핵심만 발췌)
- [ ] `agents/base.py`, `agents/fundamental.py`
- [ ] 단위 테스트: mocked OpenRouter로 출력 스키마 검증
- [ ] `agents/technical.py` 동일 패턴
- [ ] `agents/reviewer.py` — 두 에이전트 출력 + 데이터 컨텍스트 받아 최종 마크다운 생성

### Phase 3: 오케스트레이션 + API
- [ ] `orchestrator.py` — fetch → agents.gather → reviewer 파이프라인, SSE 이벤트 yield
- [ ] `routes/analyze.py` — POST 엔드포인트, StreamingResponse(media_type="text/event-stream")
- [ ] `storage/jobs.py` — SQLite 저장 (jobId, request, outputs, report)
- [ ] `routes/jobs.py` — GET 조회

### Phase 4: 프론트엔드
- [ ] `app/page.tsx` + `InputForm.tsx` (asset 입력 + 날짜 picker + 모델 드롭다운)
- [ ] `app/analyze/[jobId]/page.tsx` — SSE 구독
- [ ] `lib/sse.ts` — EventSource 훅 (`useSSE`)
- [ ] `ProgressTracker.tsx` — data fetch / 2 agents / reviewer 각 카드 상태 표시
- [ ] `ReportViewer.tsx` — `react-markdown` + `remark-gfm` (표 지원) + 다운로드 버튼

### Phase 5: 통합 검증
- [ ] e2e: 브라우저에서 `NVDA` + `2026-05-13` 입력 → 보고서 출력 확인
- [ ] 에러 케이스: 잘못된 티커, OpenRouter 429, 데이터 소스 다운
- [ ] `README.md`에 실행 방법 (개발/도커 모두) 추가
- [ ] 비용·토큰 사용 로그 확인

### Phase 6 (확장, 별도 일정)
- 한국 종목 지원 (`data/krx.py`, `data/dart.py`)
- 5개 영역 확장 (산업·거시·심리 에이전트 추가)
- 인증·결제·rate limit
- Redis 큐로 비동기 분리

## 9. 비용 / 성능 가정

| 항목 | 가정 |
|------|------|
| 분석 1건 토큰 사용 | 입력 ~30k + 출력 ~10k = 40k tokens (2 agents + reviewer) |
| OpenRouter 비용 (GPT-OSS 120B) | 입력 $0.15/M + 출력 $0.60/M = 약 $0.011 / 분석 |
| 응답 시간 | data fetch 5~15s + 2 agents 병렬 20~40s + reviewer 15~30s = **40s ~ 85s** |
| 데이터 API 비용 | NewsAPI Developer plan 무료, 그 외 무료 |

> 모델 가격은 OpenRouter 시점 카탈로그에서 확인. 위 추정은 자릿수 가늠용.

## 10. 보안·운영

- OpenRouter / 외부 API 키는 `.env`, `.env.local`에만 두고 Git 미포함 (현행 `.gitignore` 확장)
- 백엔드는 CORS를 프론트엔드 출처에만 허용
- 요청당 분석 1건 제한 (간단 in-memory rate limit) — 추후 redis 기반으로 교체
- 사용자 입력 자산명 검증 (정규식 + yfinance lookup 결과 매칭)
- 작업 결과는 SQLite에 저장 (개인정보 없음 — 자산명·결과만)
- 에러 메시지에 API 키·내부 경로 노출 금지

## 11. 미해결·후속 결정 사항

| 항목 | 옵션 | 결정 시점 |
|------|------|----------|
| Gemma 모델 정확한 ID | OpenRouter 카탈로그 확인 | Phase 1 직전 |
| 뉴스 API | NewsAPI vs Tavily vs RSS | Phase 1 |
| SQLite vs Postgres | MVP는 SQLite, 확장 시 Postgres | Phase 6 |
| 결과 영구 저장 vs TTL | TTL 30일? | Phase 5 |
| 분석 결과 PDF 내보내기 | 우선순위 낮음 | Phase 6+ |
| 한국 종목 데이터 소스 | DART OpenAPI + KRX | Phase 6 |

## 12. 부록 — 기존 자산 재사용

본 프로젝트는 기존 SK하이닉스 하네스의 자산을 재사용한다:

| 기존 자산 | 재사용 위치 | 변환 |
|---------|----------|------|
| `.claude/agents/fundamental-analyst.md` | `backend/app/prompts/system/fundamental.md` | Claude Code 도구 호출 제거, JSON 출력 지시 추가 |
| `.claude/agents/technical-analyst.md` | `backend/app/prompts/system/technical.md` | 동일 |
| `.claude/agents/integrator-reviewer.md` | `backend/app/prompts/system/reviewer.md` | 동일 |
| `.claude/skills/equity-research-method/references/valuation.md` | `backend/app/prompts/methodology/valuation.md` | 변경 없음 |
| `.claude/skills/equity-research-method/references/technical.md` | `backend/app/prompts/methodology/technical.md` | 변경 없음 |
| `.claude/skills/equity-research-method/references/citations-and-disclaimers.md` | `backend/app/prompts/methodology/citations.md` | 변경 없음 |
| `SK하이닉스_주식분석_보고서_20260513.md` | (참고용) | 출력 포맷 레퍼런스로만 사용 |

산업·거시·심리 에이전트와 한국 종목 데이터는 Phase 6에서 동일 패턴으로 확장.
