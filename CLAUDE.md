# my_city - 국가 시뮬레이션 갓게임 프로젝트

이 파일은 Claude Code가 프로젝트 작업 시 항상 참고하는 컨텍스트 파일입니다. 작업을 시작하기 전에 이 문서 전체를 읽고, 아래 "지금 할 일"부터 순서대로 진행하세요.

## 프로젝트 한 줄 요약

플레이어는 "신"이 아니라 "조언자"다. 국가는 AI가 전부 자동으로 통치(정책/자원/외교/전쟁)하고, 플레이어는 클릭 기반 조언으로 방향만 유도할 수 있다. 승패 조건 없음. 다른 국가들도 각자 성향에 따라 완전 자율로 발전한다.

## 기술 스택 (확정)

**백엔드**
- Python + FastAPI (비동기)
- SQLAlchemy 2.0 (async) + SQLite (개발 단계, 이후 PostgreSQL 전환 가능하게 설계)
- 백그라운드 루프: asyncio task (Celery/Redis는 지금 단계에서 도입하지 않음)
- 실시간 통신: FastAPI WebSocket (표준 기능만 사용, 별도 라이브러리 없음)
- LLM: Anthropic SDK (`anthropic` 패키지) - 조언 카드 생성, 개연성 판단용. 초기 단계에서는 하드코딩으로 대체하고 나중에 연결

**프론트엔드**
- Vue 3 (Composition API) + Vite
- Pinia (상태 관리)
- 맵 렌더링: Canvas 2D API (초기 단계, WebGL/Pixi.js는 나중에 필요해지면 전환)
- 웹소켓: 네이티브 WebSocket API

**원칙**
- 인프라는 가볍게 유지한다. 지금 필요 없는 건(Redis, Celery, WebGL, Postgres) 나중에 필요해질 때 붙인다.
- 핵심 루프가 재밌는지 검증하는 게 최우선 목표다. 기능을 다 채우기 전에 최소 단위로 계속 실행해보고 확인한다.

## 폴더 구조 제안

```
my_city/
├── CLAUDE.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   └── game_clock.py
│   │   ├── models/
│   │   ├── routers/
│   │   ├── services/
│   │   └── db.py
│   ├── requirements.txt
│   └── tests/
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── stores/
    │   ├── App.vue
    │   └── main.js
    ├── index.html
    └── package.json
```

## 전체 기획 참고 문서

전체 시스템(맵 11종, 테크트리, 위인, 조언, 전쟁/독립, 시간 시스템, API 스펙 전체)은 별도 설계 문서에 정리되어 있습니다. 세부 로직을 구현할 때는 아래 항목별로 이 CLAUDE.md보다 그 문서를 우선 참고하세요.

- 국가 AI 판단 구조 (룰 기반 + LLM 하이브리드)
- 테크트리 그래프 스키마 및 검증 로직 (선행조건 + 시대 개연성)
- 위인 등장 확률 공식 (`spawn_probability_base` 기반, 플레이어가 소환하지 않고 자동 판정)
- 조언 카드 생성 프롬프트 구조
- 시즌(월 단위) 오케스트레이션 루프 6단계
- 전쟁/점령/독립 상태 머신
- FastAPI 엔드포인트 전체 목록
- 튜토리얼/가이드북 구성

(설계 문서 링크: 대화 중 전달된 game_design_final.md 참고. 파일이 없으면 사용자에게 요청할 것.)

## 개발 순서 (반드시 이 순서로, 한 단계씩 완료하고 실행 확인 후 다음으로)

### 1단계: 게임 클록 (지금 여기서 시작)

**목표**: 시간이 흐르는 느낌부터 눈으로 확인한다. 국가도, 테크트리도, LLM도 아직 없음.

**백엔드**
- `GameClock` 클래스 구현 (아래 스펙 그대로)
- FastAPI 앱에 웹소켓 엔드포인트 `/ws/{session_id}` 하나
- 배속 변경 REST 엔드포인트 `POST /api/session/{session_id}/clock/speed`
- 서버 시작 시 1초 주기 백그라운드 asyncio task로 clock.tick(1) 호출

(day/hour 필드는 실제로 갱신되지 않아 제거함 — tick 단위는 월 고정. 체감 속도는 `real_seconds_per_month_base` 값으로만 조절한다.)

```python
class GameClock:
    def __init__(self, real_seconds_per_month_base: float = 6):
        self.base_interval = real_seconds_per_month_base
        self.speed = "normal"  # paused | normal | fast | fastest
        self.accumulated_seconds = 0.0
        self.current_date = {"year": 1, "month": 1}

    def get_interval(self):
        multiplier = {"paused": None, "normal": 1, "fast": 2, "fastest": 4}[self.speed]
        if multiplier is None:
            return None
        return self.base_interval / multiplier

    async def tick(self, delta_seconds: float, on_month_advance):
        interval = self.get_interval()
        if interval is None:
            return
        self.accumulated_seconds += delta_seconds
        while self.accumulated_seconds >= interval:
            self.accumulated_seconds -= interval
            self._advance_one_month()
            await on_month_advance(self.current_date)

    def _advance_one_month(self):
        self.current_date["month"] += 1
        if self.current_date["month"] > 12:
            self.current_date["month"] = 1
            self.current_date["year"] += 1
```

- `on_month_advance`는 지금 단계에서는 웹소켓으로 `{"event_type": "month_advanced", "payload": {"current_date": ...}}` 브로드캐스트만 하면 됨. 국가 로직은 2단계에서 붙인다.

**프론트엔드**
- 화면 우측 상단에 날짜 텍스트 (년/월/일/시)
- 그 아래 버튼 4개: 일시정지 / 1x / 2x / 4x
- 버튼 클릭 시 REST로 속도 변경 요청
- 웹소켓 연결해서 `month_advanced` 이벤트 수신 시 날짜 텍스트 갱신

**완료 기준**: 브라우저에서 배속 버튼 누르면 날짜가 실제로 눈에 보이는 속도로 빨라지고 느려지는 게 확인되면 1단계 끝.

### 2단계: 국가 지표 1개 국가만

- 국가 1개(플레이어) 생성, 경제력/안정도/군사력/교육 등 지표를 DB에 저장
- 매 월 진행마다 지표를 간단한 룰(예: 랜덤 소폭 변동 + 약간의 증가 추세)로 갱신
- 화면에 지표 숫자가 표시되고, 시간이 지나며 바뀌는 걸 확인
- LLM 아직 사용 안 함
- 초기 국가는 원시시대 수준으로 시작한다는 컨셉이라 지표 초기값은 낮게(5 내외) 잡음. 테크트리/시대 시스템은 5단계 이후에 제대로 설계.

### 3단계: 조언 카드 (하드코딩)

- 고정된 선택지 3개를 반환하는 API (LLM 없이 하드코딩)
- 프론트에 조언 팝업 UI, 카드 클릭 시 선택 결과가 국가 지표에 간단히 반영되는 것 확인
- 여기까지 되면 "핵심 루프"가 완성된 것 (관찰 + 클릭 개입 + 시간 흐름)

### 4단계: LLM 연결

- 3단계의 하드코딩된 조언 카드를 Anthropic API 호출로 교체
- 국가 상태를 프롬프트에 넣어서 실제 맥락에 맞는 선택지 생성

### 5단계 이후

- 테크트리, 위인, 전쟁/외교, 맵 절차적 생성, 다국가 확장 등을 순차 추가 (설계 문서 참고)

## 작업 방식

- 한 단계 끝날 때마다 실제로 서버 띄우고 브라우저에서 확인한 다음 다음 단계로 넘어간다.
- 큰 리팩토링이나 구조 변경이 필요하면 먼저 사용자에게 이유를 설명하고 진행한다.
- 새 패키지를 추가할 때는 `requirements.txt` / `package.json`에 반영하고 어떤 목적인지 간단히 언급한다.
