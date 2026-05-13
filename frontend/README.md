# Equity Research Frontend

Next.js 14 (App Router) 기반 프론트엔드. 백엔드 FastAPI 서버에 SSE로 연결한다.

## 로컬 실행

```bash
# 1. 의존성 설치
npm install

# 2. 환경변수 (선택, 백엔드 URL 변경 시)
cp .env.local.example .env.local

# 3. 개발 서버
npm run dev
```

확인: <http://localhost:3000>

`/api/*` 요청은 `next.config.mjs`의 rewrites로 백엔드(`NEXT_PUBLIC_BACKEND_URL`, 기본 `http://localhost:8000`)로 프록시된다.

## 빌드 / 타입 체크

```bash
npm run build
npm run typecheck
```

## 디렉토리

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx              # Phase 4에서 입력 폼 추가
│   ├── analyze/[jobId]/      # Phase 4에서 추가
│   └── globals.css
├── components/                # Phase 4에서 추가
├── lib/                       # Phase 4에서 추가
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
└── postcss.config.mjs
```

상세 설계: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
