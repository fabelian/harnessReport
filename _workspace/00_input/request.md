# 사용자 요청 노트

## 원본 요청
"sk하이닉스 분석해줘"

## 파싱 결과
- **종목**: SK하이닉스 (000660.KS)
- **요청 범위**: 주식 가치 다관점 분석 - 펀더멘털·기술적·산업·거시·시장심리 5개 영역 병렬 분석 후 통합 보고서
- **분석 기준일**: 2026-05-13 (현재 일자 기준 최근 거래일 종가)
- **강조 영역**: 명시되지 않음 → 5개 영역 균등 비중
- **시나리오 가중치**: 명시되지 않음 → Bullish / Base / Bearish 균등
- **출력 경로**: default → `SK하이닉스_주식분석_보고서_20260513.md`
- **실행 모드**: 초기 실행 (`_workspace/` 부재)

## 작성 원칙
- 사실 / 추정 / 의견 3단 구분
- 모든 수치는 단위·시점·출처 표기
- 1차 자료 우선 (DART, 회사 IR, KRX, BOK ECOS, TrendForce 등)
- 임의 추정 금지, 데이터 미확보 시 "확인 필요" 명시
- 단정적 추천 금지, 시나리오·범위·트리거로 제시
- 면책 조항 + 데이터 한계 부록 필수

## 산출물 경로
- `_workspace/02_fundamental_analysis.md` (fundamental-analyst)
- `_workspace/02_technical_analysis.md` (technical-analyst)
- `_workspace/02_industry_analysis.md` (industry-analyst)
- `_workspace/02_macro_analysis.md` (macro-analyst)
- `_workspace/02_sentiment_analysis.md` (sentiment-analyst)
- `_workspace/99_qa_checklist.md` (integrator-reviewer)
- `_workspace/99_final_report.md` (integrator-reviewer)
- 최종: `SK하이닉스_주식분석_보고서_20260513.md`
