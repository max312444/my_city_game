# Regnum - 국가 시뮬레이션 갓게임 프로젝트

(프로젝트 폴더/저장소 경로는 여전히 `my_city`, `my_city_game`이지만 게임/브랜드 이름은 **Regnum**입니다.
화면 타이틀, 문서 등 사용자에게 보이는 이름은 Regnum으로 통일.)

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
- 테크트리 MVP 구현 완료: `backend/app/services/tech_service.py`에 하드코딩된 6개 노드(선행조건 그래프).
  연구는 문명처럼 시간이 걸림 — "연구" 클릭 시 비용은 즉시 차감되고 `current_research`/
  `current_research_months_left`로 진행 상태를 추적, 매달 1씩 감소하다 0이 되면 효과 적용(디미니싱
  리턴 적용) + 완료 처리. 한 번에 하나만 연구 가능(슬롯 1개). 시대 개연성 검증 로직은 아직 없음 —
  설계 문서 확보되면 제대로 확장. 프론트는 좌측 `TechPanel.vue`.
- 테크트리 UI는 지금은 의도적으로 단순 리스트(TODO): 나중에 문명 스타일 노드+연결선 그래프로
  교체 예정(왼쪽 메뉴 클릭 → 전체화면/오버레이로 로드맵 펼치기). 노드가 10개 이상으로 늘어나는
  시점에 전환하는 게 효율적이라고 판단해 지금은 미룸.
- 그 외 대화 중 추가된 경제 시스템: 월 수입(경제력×5) - 월 지출(군사력×2+교육×1+안정도×0.5) = 순수입이
  국고에 누적. 국고는 마이너스(파산) 가능, `is_bankrupt` 플래그로 노출.
- 조언(광고 배너) 효과는 지표당 ±8 이하로 작게 유지 — 플레이어는 조언자일 뿐이라는 원칙을 수치로도 반영.
- 조언 제한시간(15초)은 게임 시계가 일시정지되면 함께 멈춘다 (`Session.tick_advice`, 매 초 클럭 루프에서 호출).
- 인구 시스템 추가: `population`(초기 50, 상한 없음 — 나중에 정복으로 수용 인구 늘리는 거 고려), `land_capacity`
  (초기 1000, 지금은 고정값, 밀집도=인구/수용인구 표시). "도시 만족도"(안정도 기반, 0.3~1.0)는 지금 화면
  표시용일 뿐 인구 증감에는 관여하지 않음(식량으로 대체, 아래 항목). 인구가 많을수록 경제력·군사력의
  월간 상승폭과 월 수입이 `population_factor = sqrt(population / 50)` 배수로 커짐. "도시 인기도"는 아직
  별도 구현 안 함 — 위인/불가사의 등 나중 콘텐츠 생기면 분리해서 이민 유인 등으로 확장 예정.
- 식량 시스템 추가(문명 참고): `food_stock`(비축량, 마이너스면 기근 `is_famine`), `food_bonus`(테크로 영구
  증가). 1인당 생산 0.7 - 소비 0.6 = 기본 흑자, 농경법(+0.3)/관개시설(+0.5) 연구로 생산 보너스 누적.
  **인구 증감은 이제 식량 순생산이 결정**(안정도 기반 만족도 공식은 폐기) — 흑자면 성장, 적자 지속되면
  감소, 수용 인구 초과 시 성장 둔화/역전. `nation_service.advance_nation` 참고.
- 도시(수도+확장) 시스템은 아직 없음(TODO) — 지금은 국가 전체가 통짜 지표 하나. 나중에 맵/영토/다국가
  확장 작업과 묶어서 설계 예정: 시작 화면에서 입력한 이름을 수도 이름으로, 이후 도시 확장 시 개별
  이름을 지정할 수 있게.
- 빅 이벤트(재해+행운) 추가: `backend/app/services/disaster_service.py`의 `RANDOM_EVENTS`에 좋은/나쁜
  이벤트를 한 풀에 섞어둠(가뭄/전염병/화재/지진/홍수 vs 풍작/유전 발견/유물 발견/이민 행렬/교역 호황).
  매달 1% 확률로 하나 무작위 발생(`maybe_trigger_event`, 4%→2%→1%로 "가끔 오는 긴장감" 정도로 낮춤),
  선택지 없이 즉시 적용. 지표 효과는 %기반이라 디미니싱 리턴 적용(`nation_service.apply_random_event`),
  국고/식량 비축량 효과는 "월 수입/생산 몇 개월치" 단위라 이미 마이너스인 값도 방향이 안 꼬임. 강도는
  "완전히 망하지 않고 몇 달~2~4년이면 회복 가능한" 수준으로 튜닝(초기 설계 대비 절반 정도) — 좋은
  이벤트도 과하게 퍼주지 않도록 같이 낮춤. 프론트는 상단 중앙 `EventToast.vue`, 6초 후 자동으로 사라짐
  (선택 없이 그냥 알림).
- 위인 시스템 추가: `backend/app/services/great_person_service.py`의 `GREAT_PEOPLE`(경제/군사/학문/정치
  4개 분야 x 2명 = 8명 고정 풀). 매달 3% 확률로 자동 등장(`spawn_probability_base` 개념, 플레이어가
  소환하지 않음) — 등장 분야는 관련 지표가 높을수록 뽑힐 확률이 높음(가중 랜덤), 같은 위인은 세이브당
  절대 중복 등장 안 함(`great_person_appearances` 테이블에 등장 이력 저장). 효과 적용은 `random_event`와
  같은 함수(`apply_random_event`) 재사용. 프론트: 상단 `GreatPersonToast.vue`(7초 알림) +
  우측 컬럼 `GreatPeoplePanel.vue`(등장 이력 목록, "위인 명예의 전당"). 우측 패널들(클록/국가지표/위인)은
  `App.vue`의 `.right-column` flex 컨테이너로 묶어서 자동으로 쌓이도록 리팩터링함(개별 고정 위치 방식은
  국가지표 패널이 길어지면서 겹치는 문제가 있었음).
- 전쟁/외교 MVP 추가: 실제 다국가/맵이 없는 상태라, 우선 `backend/app/services/diplomacy_service.py`에
  고정 AI 라이벌 국가 3개(`RIVAL_TEMPLATES`, 경제/안정/군사 스탯만 가짐)를 세션별로 생성해 최소한의
  "상대"를 만들어둠 — 나중에 다국가 확장/맵 작업 때 이 라이벌들을 실제 지도상의 국가로 승격시키면 됨.
  관계는 평화/전쟁 2단계(동맹은 아직 없음, TODO). 선전포고는 즉시 가능(안정도 소폭 페널티), 평화 제안은
  상대적 군사력 기반 확률로 AI가 수락/거절. 전쟁 중엔 매달 자동으로 소규모 교전 결과가 나와 패배 측
  군사력·안정도가 깎이고, 플레이어는 추가로 전쟁 유지비(`WAR_UPKEEP_BASE + 군사력×0.2`)를 국고에서 지불.
  프론트: 좌측 컬럼에 `DiplomacyPanel.vue` 추가(TechPanel과 같은 `.left-column`), 전투 결과는 패널 하단에
  6초간 표시. 화면이 좁으면 좌측 컬럼을 스크롤해야 외교 패널이 보임(TODO: 나중에 레이아웃 다시 정리).
- 맵 UI/UX 1차 구현: `backend/app/services/map_service.py`에서 절차적으로 24x16 타일맵을 생성
  (평원/숲/산/물/사막 5종, 클러스터 성장 알고리즘으로 뭉치게 배치, 외부 라이브러리 없이 순수 랜덤워크).
  세션당 한 번만 생성하고 `game_maps` 테이블에 저장(재접속해도 같은 맵 유지, "새로 만들기" 시 삭제).
  프론트는 `MapCanvas.vue`가 Canvas 2D로 전체 화면 배경에 그리고, 그 위에 기존 패널들이 얹히는 구조
  (z-index 없이 DOM 순서로 배경 처리). 수도 위치는 항상 지도 중앙에 고정, 국가 이름 라벨 표시.
  아직 없는 것(TODO): 실제 영토 소유권/타일 클릭 상호작용, 다국가 확장과의 연동, 문명 스타일 카메라 이동/줌.
- 맵 UI/UX 2차 개선(문명 스타일 요청 반영): `map_service._place_rival_capitals`가 라이벌 3개의 도시 위치도
  함께 생성해서 지도에 반환(`rival_capitals`). **주의**: 좌/우 UI 패널이 화면 세로 전체를 차지하므로
  라이벌 배치는 반드시 중앙 상단/하단 "안전지대"(x: 33~67%)에만 놓을 것 — 모서리나 좌우 가장자리에
  놓으면 라벨이 패널과 겹침(한 번 겪은 버그). `MapCanvas.vue`에 추가된 것: (1) 타일별 디테일 —
  숲=나무 실루엣, 산=눈 덮인 봉우리, 물=파도선, 사막=모래 점, 초원=이따금 풀 무늬, 타일마다 결정론적
  해시로 색 지터(hashTile 함수, 매 리렌더마다 동일하게 유지). (2) 수도/라이벌 주위에 점선 테두리 +
  방사형 그라디언트로 "영역" 표시(TERRITORY_RADIUS_TILES=3.1, 플레이어는 파란색, 라이벌은 국가별
  고유색). (3) 인구(플레이어)/경제력(라이벌, 대용 지표)에 따라 마을→소도시→도시→대도시 4단계로
  건물 실루엣이 늘어나고 커지는 도시 성장 비주얼(tierFromSize). (4) 전쟁 중인 라이벌 도시 위에 ⚔ 표시.
  전부 이미지 에셋 없이 Canvas 2D 도형만으로 구현(의존성 추가 없음).
- 로그인/회원가입 시스템 추가 — 예전에는 "이름만 입력하면 그게 곧 세이브 키"였는데, 이제 진짜 계정
  개념이 생김. `backend/app/models/user.py`(`users` 테이블: username unique, password_hash+salt,
  display_name), `backend/app/services/auth_service.py`(PBKDF2-SHA256 100,000회 해싱, 외부 의존성
  없이 표준 라이브러리 `hashlib`/`secrets`만 사용). 회원가입은 아이디/비밀번호/이름, 로그인은
  아이디/비밀번호만. 아이디 중복확인 엔드포인트(`GET /api/auth/check-username`) 별도 제공, 프론트
  회원가입 폼에 "중복확인" 버튼으로 노출. **중요한 설계 결정**: 로그인 성공 시 `username`을 그대로
  기존 `session_id`로 재사용함 — 게임 데이터를 다루는 기존 엔드포인트(국가/테크/외교/맵 등)를 전혀
  건드릴 필요 없이 인증 레이어만 얹은 것. 회원가입 시 입력한 "이름"은 국가 이름 초기값으로 자동
  반영(`nation_service.init_nation_name`). 예전의 "이어하기/새로 만들기" 개념은 사라짐 — 로그인 =
  이어하기, 회원가입 = 새 계정 겸 새 게임. 세이브 삭제("새로 시작") 기능은 지금 진입 화면에서 뺐음
  (TODO: 나중에 게임 내 메뉴로 다시 넣기). 프론트: `LoginScreen.vue`가 기존 `StartScreen.vue`를
  대체(파일 삭제됨), 탭 전환(로그인/회원가입) UI.
- 프로젝트 이름을 **Regnum**으로 확정(플레이어=왕이 아니라 조언자 컨셉과 어울리는 라틴어 "왕국/통치").
  폴더/저장소 경로는 여전히 `my_city`/`my_city_game`이지만, 화면 타이틀·README·package.json 등 사용자
  대면 브랜딩은 전부 Regnum으로 통일함.
- 맵 UI/UX 3차 개선("유치해 보인다"는 피드백 반영, 실사 이미지는 에셋이 없어서 불가능 — 대신 절차적
  텍스처를 훨씬 자연스럽게 개선): `MapCanvas.vue`에 결정론적 Perlin 유사 노이즈(`makeNoise2D`, 외부
  라이브러리 없이 직접 구현)로 지형 베이스 텍스처를 만듦 — 타일마다 flat fill 하는 대신, 지형별 두
  색상(low/high) 사이를 노이즈 값으로 블렌딩해서 타일 경계를 넘나드는 연속적이고 얼룩덜룩한 자연스러운
  질감을 만들어냄. 성능을 위해 실제 화면 해상도가 아니라 타일당 24px 고정 해상도의 오프스크린 캔버스에
  픽셀 단위로 한 번만 그리고(`buildTerrainTexture`, 지형 배열이 안 바뀌면 캐시 재사용), `drawImage`로
  확대해서 그림(디바이스 픽셀 단위로 매번 노이즈 계산하는 것보다 훨씬 빠름). 숲/산/물/사막 디테일도
  레이어드 블롭·그라디언트·다중 능선으로 업그레이드. **영역 표시를 원형 → 칸(정사각형) 단위로 변경**
  (`drawTerritoryBlock`, `TERRITORY_RADIUS_BY_TIER = [1,2,3,4]`) — 마을은 수도 타일 기준 반경 1칸
  (3x3), 소도시 반경 2칸(5x5), 도시 3칸(7x7), 대도시 4칸(9x9)으로 도시 성장 단계(`tierFromSize`, 도시
  비주얼과 동일 기준 재사용)와 정확히 연동. 체비쇼프 거리로 정사각 블록 판정.
- **영토를 자동 성장 정사각형 → 돈으로 사는 타일 구매제로 전면 교체** (문명 스타일 피드백 반영).
  `backend/app/models/territory.py`의 `OwnedTile`에 `owner` 컬럼 추가(`"player"` 또는 라이벌의
  `rival_id`) — 세션당 타일 하나는 오직 한 세력만 소유 가능. `territory_service.py`:
  `ensure_initial_territory`/`ensure_rival_territory`로 플레이어와 라이벌 모두 수도 주변 반경 1칸
  (3x3, 9칸)에서 동일하게 시작(공평한 출발선). `purchase_tile`(플레이어 전용, 유료)은 (1) 아무도
  소유하지 않은 타일인지 전역 체크 (2) 플레이어 자신의 기존 영토와 인접한지 체크 (3) 물 타일 금지
  (4) 비용(`80 + 12 * 보유 타일 수`)을 국고에서 차감 — 이 순서로 검증. `expand_rival_territory`는
  라이벌용 확장 함수로, 비용 없이 자기 영토와 인접한 미소유·비수몰 타일 중 무작위로 하나씩 점유.
  **버그 수정(사용자 발견)**: 처음엔 라이벌 영토가 프론트에서 경제력 기반으로 매번 다시 계산되는
  "가상의" 정사각형이라 플레이어가 구매한 땅과 그냥 겹쳐버리고, 라이벌은 경제력만 오르면 즉시
  대도시 반경(4칸)까지 순간이동하듯 영유권을 주장하는 문제가 있었음 → 라이벌도 플레이어와 동일하게
  실제 DB에 타일을 하나씩 점유해나가도록 변경(`diplomacy_service.advance_rivals`가 매달 라이벌별로
  `min(0.25, economy/400)` 확률로 `expand_rival_territory` 1회 시도), 구매/확장 모두 "이미 다른
  세력이 소유한 타일"이면 무조건 거부되므로 이제 겹침 자체가 구조적으로 불가능. (순환 임포트 주의:
  `map_service`가 모듈 최상단에서 `diplomacy_service`를 임포트하므로, 반대 방향 임포트는
  `advance_rivals` 함수 안에서 지연 임포트로 처리.) 기존 SQLite 파일에 이미 있던 `owned_tiles`
  테이블은 `ALTER TABLE`로 `owner` 컬럼을 추가해 마이그레이션(기존 행은 전부 `"player"`로 간주 —
  `create_all`은 기존 테이블에 컬럼을 추가해주지 않으므로 스키마 변경 시 항상 수동 마이그레이션 필요).
  프론트 `MapCanvas.vue`: 도시 성장 단계(`tierFromTileCount`)를 인구/경제력 대신 **실제 보유 타일 수**
  기준으로 변경(마을<15, 소도시<30, 도시<60, 대도시 60+). 캔버스 클릭 → 화면 좌표를 타일 좌표로 변환 →
  구매 확인 팝업(HTML 오버레이, 비용/에러 표시) → 구매 확정 시 `territory_service.purchase`. 각 세력의
  영토는 더 이상 고정 정사각형이 아니라 실제 소유 타일 집합을 채우고, 소유하지 않은 이웃과 맞닿는
  변에만 테두리를 그려서 모양이 자연스럽게 들쭉날쭉해짐(`drawOwnedTerritory`). `GET /territory`는
  `{tiles: 플레이어 소유만, all: 전체 [{x,y,owner}]}`를 반환하고, 웹소켓 `territory_updated` 이벤트도
  `{all: [...]}`로 통일(구매든 라이벌의 자동 확장이든 동일 이벤트로 모든 클라이언트에 브로드캐스트).
- 도시 이미지를 좀 더 자연스럽게: `MapCanvas.vue`의 `drawCity`에 지면 클리어링(반투명 타원), 건물별
  드롭섀도, 세로 그라디언트 음영, 여러 지붕 색상 로테이션을 추가해 예전의 납작한 단색 사각 블록보다
  입체감 있게 개선.
- 계정 닉네임과 국가(도시) 이름 분리: 회원가입 때 입력한 `display_name`은 더 이상 국가 이름에 자동
  반영되지 않음(`nation_service.set_nation_name`이 `init_nation_name`을 대체). 국가는 항상
  `name = session_id`(계정 아이디)로 시작하고, 프론트는 로그인 직후 `nation.name === sessionId`이면
  아직 이름을 안 지은 것으로 판단해 `NationNamePrompt.vue`(전체화면 프롬프트)를 띄움. 이름을 정하면
  게임 화면으로 진입. 이후에도 `GameMenu.vue`의 "설정" 탭에서 언제든 다시 이름 변경 가능.
- 화면 레이아웃 재편(사용자 요청): 인구/식량/재화/경제력 등 핵심 지표를 화면 상단 중앙에 가로 한 줄
  배치(`TopHud.vue`, `top:16px` 고정 pill 바)로 옮기고, 기존에 항상 떠 있던 `NationPanel`/
  `GreatPeoplePanel`은 삭제. 우측 상단 시계 패널 밑에 `GameMenu.vue`("☰ 메뉴" 버튼)를 추가 — 클릭하면
  모달이 열리고 탭 3개(국가 통계/위인 명예전당/설정)로 예전 패널들의 내용을 대체. `EventToast`/
  `GreatPersonToast`는 TopHud와 안 겹치게 각각 `top:76px`/`top:150px`로 아래로 밀어냄.
  **레이아웃 버그(사용자 발견 후 수정)**: `.right-column`에 고정 `width:160px`를 줬더니 시계 패널의
  배속 버튼 4개("일시정지"/1x/2x/4x)가 들어갈 공간이 부족해 "일시정지" 텍스트가 세로로 한 글자씩
  쪼개져 보이는 버그 발생 → `width` 제거하고 각 자식에 `min-width:190px`만 주는 방식으로 수정, 버튼에도
  `white-space:nowrap`/`flex-shrink:0` 추가.
- **전투/영토 침략 시스템**: 전쟁 중 전투에서 이기면 패자의 국경 타일 하나를 실제로 빼앗아온다.
  `territory_service.capture_tile(session_id, winner, loser, protected_tiles)` — 승자가 이미 소유한
  타일과 맞닿아 있는(체비쇼프 거리 1) 패자 소유 타일 중에서만 무작위로 하나 골라 `owner`만 바꿔치기
  (행을 지우고 새로 만드는 게 아니라 기존 행의 소유자만 갱신 — 히스토리/ID 유지). **국경이 서로 안
  맞닿아 있으면 점령 자체가 발생하지 않음** — 침략은 실제 접경에서만 가능하다는 규칙을 의도적으로
  강제(먼 나라를 이겨도 땅은 못 뺏음, 플레이어가 먼저 그 방향으로 영토를 사서 접근해야 함). 수도 타일은
  `protected_tiles`로 항상 보호되어 절대 뺏기지 않음(이 게임엔 "국가 멸망/정복" 상태가 없어서 수도를
  잃으면 도시 라벨이 사라지는 등 상태가 깨지기 때문 — 의도적 설계 제약). `diplomacy_service.
  advance_rivals`의 매달 전투 판정 로직에서 승패가 갈릴 때마다 (승자, 패자, 라이벌명) 튜플을 모아뒀다가,
  라이벌 영토 자동 확장 처리 직후에 한 번에 `capture_tile` 호출 — 성공하면 전쟁 보고
  (`reports`)에 "OO의 국경 지역을 점령했습니다" / "OO에게 국경 지역을 빼앗겼습니다" 문구를 추가하고
  `territory_changed=True`로 웹소켓 `territory_updated` 브로드캐스트를 트리거. 프론트는 추가 코드 없이
  그대로 작동함 — `DiplomacyPanel.vue`가 이미 `reports` 배열을 그대로 렌더링하고, `MapCanvas.vue`는
  이미 `territoryStore.allTiles` 변경을 watch해서 다시 그리기 때문(소유자만 바뀐 타일도 자동으로 색이
  바뀜). 검증: 격리된 파이썬 스크립트로 30개월치 전쟁 시뮬레이션 돌려서 점령 메시지 발생 확인 + 수도
  타일이 30번 내내 원래 주인 그대로인 것 확인. 실제 브라우저(CDP)로도 확인했는데, 선전포고한 상대국이
  플레이어 영토와 아직 안 맞닿아 있는 케이스라 점령이 안 일어나는 것도 확인함(의도한 대로 "접경 없으면
  점령 없음" 규칙이 지켜짐 — 실제 플레이라면 그 방향으로 땅을 사서 접근해야 침략이 가능해짐).

## 기반 다지기 (기능 추가 속도를 인프라가 못 따라가고 있다는 자체 진단 이후)

여기까지 기능이 빠르게 쌓이는 동안 테스트/마이그레이션/세션 지속성 같은 기반이 계속 뒤로 밀렸다는
자체 회고 후, 사용자가 "전부 다 가보자, API 키 빼고는 전부 무료 기반으로"라고 요청해서 아래 5가지를
전부 처리함. 새로 추가한 패키지(alembic, pytest, pytest-asyncio, httpx)는 전부 무료 오픈소스, 유료
서비스는 전혀 추가하지 않음.

- **세션 새로고침 지속**: `frontend/src/stores/session.js`가 `sessionId`를 `localStorage`
  (`regnum_session_id` 키)에 저장/복원하도록 변경. 브라우저 새로고침해도 재로그인 불필요. 저장/조회
  모두 try/catch로 감싸서 시크릿 모드 등 스토리지 차단 환경에서도 그냥 "로그아웃 상태"로 안전하게
  폴백. `GameMenu.vue`의 로그아웃은 `setSessionId(null)`을 호출하므로 자동으로 localStorage도 비워짐.
- **Alembic 도입**: `backend/alembic/`에 마이그레이션 스캐폴드 추가. `alembic/env.py`가 모든 모델
  모듈을 직접 import해서 `Base.metadata`를 완전히 채운 뒤 autogenerate에 사용하고, 앱은 async
  `sqlite+aiosqlite` 드라이버를 쓰지만 Alembic 자체는 동기로 도니까 `env.py`에서 URL의 드라이버만
  `sqlite`(표준 라이브러리 sqlite3)로 바꿔치기함. **SQLite는 `ALTER COLUMN`을 직접 지원하지 않으므로
  `render_as_batch=True`를 양쪽 `context.configure()`에 필수로 설정**(배치 모드가 내부적으로
  테이블을 통째로 재생성) — 이거 없으면 컬럼 타입/제약조건을 바꾸는 마이그레이션이 SQLite에서
  전부 실패함. 기존 dev DB(`my_city.db`, 실제 오래 플레이한 세이브 포함)에 대해 첫 마이그레이션을
  적용하기 전에 항상 파일을 복사해 백업했고, 적용 후 행 수/스키마를 직접 확인하는 절차를 습관화함.
  **앞으로 스키마를 바꿀 때는 절대 수동 `ALTER TABLE`을 하지 말고 항상
  `alembic revision --autogenerate -m "설명"` → 생성된 파일 검토(특히 SQLite는 컬럼 추가 시
  `server_default`를 꼭 넣어야 기존 행이 NOT NULL 위반으로 안 깨짐) → `alembic upgrade head` 순서로
  진행할 것.** `app/db.py`의 `init_db()`(`create_all`)는 완전히 새로운 빈 DB를 위한 안전망으로만
  남겨두고, 기존 DB의 스키마 변경은 전적으로 Alembic이 담당하는 하이브리드 방식으로 정리.
- **자동화된 백엔드 테스트 suite 추가**: `backend/tests/`에 pytest 기반 테스트 62개(auth/nation
  계산식/테크트리/재해/위인 중복방지/외교/영토구매·침략/맵 생성/session_manager 오케스트레이션까지
  전부 커버, `test_api_smoke.py`는 httpx `ASGITransport`로 실제 FastAPI 앱을 서버 기동 없이 그대로
  호출하는 end-to-end 스모크 테스트). **핵심 설계: 절대 진짜 dev DB(`my_city.db`)를 건드리지 않음** —
  `app/db.py`가 `DATABASE_URL` 환경변수를 읽도록 바꾸고, `tests/conftest.py`가 다른 모든 import보다
  먼저 이 환경변수를 `backend/tests/test_regnum.db`(gitignore 처리됨)로 설정한 뒤에야 `app.db`를
  import함 — 순서가 뒤바뀌면 이미 캐시된 모듈이 진짜 DB를 보게 되므로 순서가 중요. 매 테스트는
  고유한 `session_id` fixture(uuid 기반)를 받아 같은 테스트 DB 파일을 공유해도 서로 안 겹치게 함.
  엔진에 `poolclass=NullPool` 추가(테스트마다 별도 이벤트 루프를 쓰는 pytest-asyncio 환경에서 커넥션
  풀링이 루프 경계를 넘나들며 깨지는 문제를 원천 차단 — SQLite는 어차피 풀링해서 얻을 이득이 거의
  없음). `pytest.ini`에 `asyncio_mode = auto`로 데코레이터 없이 `async def test_...`가 바로 동작하게
  설정. 전체 62개 테스트가 3~4초 안에 끝남 — 이 정도면 스키마/서비스 로직을 고칠 때마다 매번 돌려도
  부담 없는 수준이라 습관적으로 돌릴 것.
- **순환 임포트/서비스 결합도 정리**: `map_service`가 라이벌 배치용으로 필요했던 `RIVAL_TEMPLATES`가
  원래 `diplomacy_service`에 정의돼 있었고, `diplomacy_service.advance_rivals`는 반대로
  `map_service`/`territory_service`가 필요해서 함수 내부 지연 임포트로 순환을 피해왔음(오늘 영토
  침략 기능 추가할 때도 이 패턴을 또 씀 — 기능이 늘수록 이런 땜빵이 계속 늘어날 구조였음). 근본
  해결: `RIVAL_TEMPLATES`를 그 자체로는 아무것도 import하지 않는 중립 모듈
  `backend/app/data/rivals.py`로 옮기고 `map_service`/`diplomacy_service` 둘 다 거기서 가져오게
  바꿈. 그리고 `diplomacy_service.advance_rivals`가 맵/영토를 직접 건드리는 걸 완전히 그만두고, 대신
  전투 결과를 `war_outcomes`(승자/패자/이름 튜플 리스트)로만 반환하도록 시그니처를 바꿈 — 실제 타일
  변경(라이벌 자동 확장 + 전쟁 점령)은 이미 매달 모든 서비스를 순서대로 호출하는
  `session_manager.py`의 새 헬퍼 `_resolve_territory_changes()`로 옮겨서 처리. 결과적으로
  `diplomacy_service`는 이제 `map_service`/`territory_service`를 전혀 모름(지연 임포트 완전 제거),
  `map_service`↔`territory_service`의 기존 단방향 관계(map_service가 초기 영토 시딩을 위해
  territory_service를 부름)도 그대로 유지됨 — 서로 다른 서비스를 오가는 조율(orchestration) 로직은
  전부 `session_manager`처럼 "이미 모두를 알고 있는" 최상위 계층에 둔다는 원칙을 세움. 이 리팩토링은
  먼저 테스트 62개를 다 만들어 둔 다음에 진행해서 회귀 여부를 바로 확인할 수 있었음 — 순서가 중요.
- **전쟁 시스템 심화** ("한쪽만 선전포고 가능한 게 너무 얕다"는 자체 진단 반영): `RivalNation`에
  `war_months` 컬럼 추가(Alembic 마이그레이션으로 적용, 새 컬럼이라 `server_default='0'` 필수 — 안
  넣으면 기존 라이벌 행에서 NOT NULL 위반으로 실패함). 두 가지 새 메커니즘, 둘 다 이 프로젝트의 기존
  톤("작은 확률, 부드러운 수치, 완전히 망가지지 않게")을 그대로 따름:
  1. **라이벌의 선제 선전포고**: 매달, 평화 상태인 라이벌은 자신의 군사력이 플레이어보다 우세할수록
     커지는(단 최대 5%로 제한) 작은 확률로 먼저 선전포고할 수 있음(`RIVAL_AGGRESSION_CHANCE_BASE=0.01`,
     `_CAP=0.05`). 그동안 전쟁은 플레이어만 시작할 수 있었는데, 이제 "플레이어는 절대 안전하지 않다"는
     긴장감이 생김 — 다만 확률을 낮게 유지해서 매달 대비해야 하는 위협이 아니라 가끔 오는 이벤트로
     남김(기존 랜덤 이벤트/위인 확률 튜닝과 같은 철학).
  2. **전쟁 피로도**: 전쟁이 길어질수록(`war_months` 누적) 양측 안정도가 매달 추가로 깎이고
     (`WAR_EXHAUSTION_STABILITY_RATE=0.005`, 최대 12개월치까지만 누적), 그 전쟁이 그냥 "지쳐서" 평화로
     끝날 확률도 매달 커짐(`war_months * 0.02`, 최대 30%) — 그래서 플레이어가 평화 제안을 전혀 안 해도
     전쟁이 무한정 이어지지 않고 자연스럽게 정리됨. `declare_war`/`propose_peace` 성공 시 모두
     `war_months`를 0으로 리셋. 프론트 `DiplomacyPanel.vue`는 "전쟁" 배지 옆에 "N개월째"를 표시.
     새 메커니즘 6개 테스트로 검증(라이벌 선공/미공격, war_months 누적, 장기전 자동 종전, 기존 승패
     로직 무손상).
- **좌측 레이아웃 개선** ("테크트리/외교 패널 때문에 지도 왼쪽이 안 보이고 맵이 좁다"는 스크린샷 피드백
  반영): 예전엔 `TechPanel`/`DiplomacyPanel`이 `App.vue`의 `.left-column`에 항상 떠 있는 불투명
  패널이라 지도 왼쪽 ~250px가 영구적으로 가려져 있었음. 세 가지 방향(메뉴로 통합 / 접었다 펴는 서랍형
  / 지도 자체를 리사이즈하는 진짜 반응형) 중 사용자가 "접었다 펴는 서랍형"을 선택. 새
  `frontend/src/components/LeftDrawer.vue`가 `TechPanel`+`DiplomacyPanel`을 감싸서, 평소엔 화면
  왼쪽 가장자리에 세로 텍스트로 된 작은 탭("▶ 테크 · 외교")만 남기고 `transform: translateX(-100%)`로
  숨겨둠 — 지도가 기본 상태에서 완전히 꽉 차 보임. 탭 클릭 시 `transform: translateX(0)`로 슬라이드
  아웃(0.25s transition)하면서 탭 자체도 패널 오른쪽 끝(252px)으로 따라 이동(`◀` 아이콘으로 전환).
  `App.vue`의 `.left-column` div와 개별 import는 제거하고 `<LeftDrawer />` 하나로 교체. `TechPanel`/
  `DiplomacyPanel` 컴포넌트 내부는 전혀 안 건드림(이미 자체 완결된 220px 폭 카드형 UI라 드로어 안에
  그대로 넣기만 하면 동작). CDP로 collapsed → expanded → collapsed 토글 왕복 확인 완료.

## 대규모 기능 확장 + 프론트 전면 재테마 (2026-09-22)

사용자가 한 메시지에 6가지를 요청("오른쪽 메뉴는 그대로 두고 국가 통계를 서랍형으로", "도시당 최대인구
대폭 증가", "도시 등급 표시를 글자 대신 이모지로", "전쟁으로 인한 멸망 구현", "수도 외 다른 도시 개설",
"라이벌끼리도 동맹/전쟁/교역 상호작용") + 이어서 GameMenu에 "메인 화면으로/저장하기/다시하기(확인
필요)" 추가 요청. 백엔드부터 구현하고(이전 세션에서 78개 테스트로 검증) 이번 세션에 프론트엔드까지
전부 마무리, 그 사이에 사용자가 "게임 로그(연대기)"와 "UI 디자인 전면 재정비"까지 추가 요청해서 함께
처리함. 아래는 전체 완료 내역.
- **최대 인구 = 보유 타일 수 기반으로 확장**: `models/nation.py`에 `LAND_CAPACITY_PER_TILE=500`,
  `compute_land_capacity(tiles) = max(1000, tiles*500)`. `nation_service.advance_nation`이
  `owned_tile_count`/`city_count` 파라미터를 받아 매달 `land_capacity`를 갱신하고, 새
  `sync_land_capacity()`로 영토 구매/전쟁 점령 직후에도 즉시 반영(다음 달까지 안 기다림) —
  `session_manager.on_month_advance`와 `main.py`의 구매 엔드포인트, `_resolve_territory_changes`
  세 군데서 호출. 대도시(60타일+) 기준 인구 상한이 이제 30,000명대로 — 예전 3,000명 문제 해결.
- **도시 설립(수도 외 추가 도시)**: 새 테이블 `cities`(`app/models/city.py`) +
  `app/services/city_service.py`. `found_city()`가 (1) 자기 소유 타일인지 (2) 수도/다른 도시와
  체비쇼프 거리 3칸 이상 떨어졌는지 (3) 비용(`2000 + 1000*기존 도시 수`) 감당 가능한지 검증. 설립된
  도시는 나라 전체 경제/식량 생산에 도시 1개당 +5% 보너스(`CITY_ECONOMY_BONUS_PER_CITY`,
  `advance_nation` 안에서 적용) — 도시별 독립 경제 시뮬레이션은 안 만들고(과도한 설계), 국가 단일
  스탯 모델은 그대로 유지한 채 보너스만 얹는 방식. 엔드포인트: `GET/POST /api/session/{id}/cities`.
- **전쟁으로 인한 멸망**: `territory_service.capture_tile`에 `allow_elimination` 파라미터 추가 —
  패자가 이미 타일 1개(자기 수도)만 남은 "최후의 저항" 상태일 때만 그 마지막 타일도 뺏을 수 있게
  허용(평소엔 여전히 수도 보호). **플레이어는 절대 멸망하지 않음** — `session_manager.
  _resolve_territory_changes`가 `allow_elimination=(loser != "player")`로 호출해서 라이벌만 멸망
  가능하게 명시적으로 제한(승패 조건 없음이라는 원래 설계 철학 유지, 라이벌 NPC만 예외). 멸망하면
  `diplomacy_service.mark_defeated()`가 `relationship="defeated"`로 표시하고, 이후
  `advance_rivals`/`advance_world` 양쪽에서 defeated 라이벌은 완전히 건너뜀(스탯 드리프트도 안 함,
  전쟁/동맹 로직도 제외). 부활은 구현 안 함(TODO로 남김 — 나중에 새 라이벌이 폐허에서 등장하는 것도
  고려해볼만함).
- **라이벌끼리 상호작용(동맹/전쟁/평화)**: 새 테이블 `rival_relationships`(`rival_a`, `rival_b`는 항상
  정렬된 순서로 저장해서 쌍당 행 1개만 존재). `diplomacy_service.advance_world()`가 매달 플레이어와
  무관하게 라이벌 쌍마다 굴러감 — 평화 중이면 소확률로 전쟁(`WORLD_WAR_CHANCE_PER_MONTH=0.01`) 또는
  동맹(`WORLD_ALLIANCE_CHANCE_PER_MONTH=0.008`), 전쟁 중이면 매달 소규모 전투(군사력 낮은 쪽이 소폭
  손해)+지쳐서 평화될 확률(`0.08`), 동맹은 가끔 깨질 수 있음(`0.02`). **의도적으로 단순화한 부분**:
  라이벌끼리는 서로 영토를 뺏지 않음(플레이어-라이벌 전쟁만 영토 이동 있음), 동맹은 순수 플레이버라
  한쪽이 전쟁 중이어도 동맹국이 자동으로 참전하지 않음(상호방위 없음) — 나중에 필요하면 확장 가능하게
  설계는 열어둠. 뉴스 문구는 기존 `war_report` 브로드캐스트에 그대로 합쳐서 보냄(별도 이벤트 안 만듦,
  `DiplomacyPanel.vue`가 이미 그 리스트를 그대로 렌더링하니 재사용). 엔드포인트:
  `GET /api/session/{id}/diplomacy/world`.
- **"다시하기" 대비 정리**: `DELETE /api/session/{id}`가 예전엔 국가/맵/영토만 지우고 라이벌·위인
  이력·(이제 추가된) 도시·라이벌 관계는 안 지웠음(잠재 버그 — 같은 계정으로 재시작하면 라이벌이
  이미 쌓인 스탯/전쟁 상태로 시작하고, 위인은 이미 등장한 걸로 처리돼서 다시 안 나옴). 이번에
  `diplomacy_service.delete_world_data()`, `great_person_service.delete_history()`,
  `city_service.delete_cities()`를 추가해서 `delete_session`이 전부 지우도록 고침 — 프론트에서
  "다시하기" 버튼 만들 때 이 엔드포인트 그대로 쓰면 됨.
- **Alembic 사용 중 겪은 함정**: 새 모델 파일(`city.py`, `rival_relationship.py`)을 만들고 바로
  `alembic revision --autogenerate`를 돌렸더니 **빈 마이그레이션**이 생성됨 — `alembic/env.py`가
  모델 모듈들을 하드코딩된 리스트로 직접 import해서 `Base.metadata`를 채우는 구조인데, 새 모델을 그
  리스트에 안 넣으면 Alembic이 그 테이블의 존재 자체를 모름. **새 모델 파일을 추가할 때마다
  `alembic/env.py`의 import 리스트에도 반드시 추가할 것** — 안 그러면 마이그레이션이 조용히 아무것도
  안 하는 채로 "성공"해버림(에러도 안 남).
- 테스트 78개로 전부 검증(신규: 인구 상한 스케일링 5개, 도시 설립 8개, 멸망 관련 캡처 로직 3개 —
  단, `advance_world`/`mark_defeated`/월드 관계 자체에 대한 서비스 레벨 테스트는 시간 관계상 아직
  못 씀, 다음 세션 TODO).

**이번 세션 프론트엔드 완료분:**
1. `TopHud.vue`를 `LeftDrawer.vue`와 같은 서랍 패턴으로 전환 — 평소엔 국가 이름 pill("▼ 국가명")만
   보이고, 클릭하면 그 아래로 7개 지표가 펼쳐짐(`max-height`/`opacity` 트랜지션). `GameMenu`(☰메뉴)는
   그대로 설정/통계 전용으로 유지.
2. `MapCanvas.vue`의 `drawCity()` 텍스트 등급(`(마을)`/`(대도시)` 등)을 이모지로 교체
   (`TIER_EMOJI = ['🏘️','🏙️','🌆','🌃']`, 도시 이름 앞에 붙임).
3. 도시 설립 UI 완성: `stores/city.js` 신설, `MapCanvas.vue`의 `handleClick`에서 자기 소유 타일 중
   수도도 아니고 기존 도시도 없는 곳을 클릭하면 `foundCityPrompt`가 열려 이름 입력 + 비용 표시 +
   건설/취소. 수도·다른 도시와 체비쇼프 거리 3칸 미만이면 즉시 에러 표시(백엔드가 최종 검증은 다시
   함). 지도에는 `drawCity(tier=0)`로 작게 렌더링. CDP로 실제 타일 2칸 구매 → 도시 건설까지 끝까지
   확인 완료.
4. 멸망 표시: `drawRuins()` 함수 추가 — `relationship: "defeated"`인 라이벌은 건물 대신 흐린 잔해
   + "💀 이름 (멸망)"으로 렌더링(완전히 안 그리는 대신 "몰락한 역사"가 지도에 남아있게). 라이벌
   자체(영토는 이미 0타일이라 자동으로 안 그려짐)에 별도 처리 불필요했음.
   `DiplomacyPanel.vue`는 `defeated` 배지 표시 + 선전포고/평화 제안 버튼 모두 숨김.
5. 세계 정세: `diplomacy.js` 스토어에 `worldRelationships`/`fetchWorldRelationships()`/`rivalName()`
   추가, `GET /diplomacy/world` 붙여서 `DiplomacyPanel.vue` 하단에 라이벌 쌍마다 ⚔(전쟁)/🤝(동맹)/
   · (평화) 아이콘으로 표시. `clock.js`의 `war_report` 웹소켓 이벤트가 올 때마다 재조회(별도 브로드캐스트
   안 만들고 기존 이벤트에 편승).
6. `GameMenu.vue` 설정 탭에 4개 버튼: "메인 화면으로 돌아가기"(로그아웃과 동일 동작), "저장하기"(매달
   자동 저장되므로 "저장되었습니다" 안내만 — 가짜 저장 로직 안 만듦), "다시하기"(주황/호박색으로
   로그아웃과 시각적으로 구분, `window.confirm(...)` 확인 후 `DELETE /session/{id}` → 새로고침),
   기존 "로그아웃"(빨강, 유지).
7. **게임 로그(연대기)**: 새 테이블 `game_logs`(`year`,`month`,`category`,`message`) +
   `log_service.py`. `session_manager.on_month_advance`가 테크 완료/이벤트/위인 등장/전쟁 보고/세계
   소식을 매달 자동으로 기록(영토 구매처럼 너무 잦은 건 제외). `GameMenu.vue`에 "게임 로그" 탭 추가 —
   열면 카테고리별 아이콘(📚⚡👑⚔️🌍🏛️)과 함께 오래된 순으로 나열되고 자동으로 맨 아래(최신)로
   스크롤됨. `DELETE /session`에도 연결해서 "다시하기" 시 로그도 같이 초기화.
8. **UI 전면 재테마("역사서/양피지" 톤, 사용자가 3가지 프리뷰 중 선택)**: `frontend/src/styles/
   theme.css` 신설 — CSS 변수(`--panel-bg`, `--accent`, `--font-heading` 등)로 색/폰트를 한 곳에서
   관리하고, `.panel`/`.panel-title` 공용 클래스 제공. Google Fonts `Noto Serif KR`(본문/한글 제목)
   + `Cinzel`(로고 "REGNUM" 전용)을 `index.html`에 추가. 기존에 컴포넌트마다 제각각이던
   하드코딩 색상(`rgba(0,0,0,0.6)`, `#4a90d9` 등)을 전부 변수로 교체 — TopHud/ClockPanel/GameMenu/
   LeftDrawer/TechPanel/DiplomacyPanel/EventToast/GreatPersonToast/AdviceBanner/LoginScreen/
   NationNamePrompt/MapCanvas의 HTML 팝업까지 전부 통일. 결과적으로 지도(Canvas, 별개 취급)를 뺀
   모든 UI 요소가 어두운 갈색/금테/세리프 폰트로 하나의 "역사서"처럼 보이게 됨.
- **버그 발견 및 수정(오늘 재테마 중 CDP로 발견)**: "세계 정세" 목록에 `"동쪽 부족 연맹 · 동쪽 부족
  연맹"`처럼 자기 자신과 짝지어진 이상한 항목이 나타남. 원인: `DiplomacyPanel.vue`의 `onMounted`가
  `fetchRivals()`와 `fetchWorldRelationships()`를 `await` 없이 동시에 호출했는데, 세션이 새로 생성된
  순간에는 두 요청 모두 `diplomacy_service._get_rivals`의 "라이벌 3개가 하나도 없으면 시딩" 로직을
  거의 동시에 통과하면서 각자 3개씩, 총 6개(라이벌당 2개 중복)를 만들어버림 — 그 중복된 rival_id 리스트로
  `itertools.combinations`를 돌리니 (a,a) 같은 자기 짝이 나온 것. 세 군데를 고침: (1)
  `DiplomacyPanel.vue`의 두 호출을 순차 `await`로 변경(실제 트리거 제거) (2) `_get_rivals`를
  "하나도 없으면 3개 다 시딩"에서 "이미 있는 rival_id는 건너뛰고 없는 것만 시딩"으로 변경(경합 폭을
  줄임) (3) `_get_relationships`가 `set(rival_ids)`로 중복 제거 후 조합을 만들도록 방어 코드 추가
  (근본 원인이 남아있어도 화면에 이상한 쌍은 절대 안 뜨게). 이미 오염된 테스트 계정 2개의 중복 행은
  수동 정리. 회귀 테스트 2개 추가(`test_get_rivals_is_idempotent_and_only_seeds_missing_ones`,
  `test_world_relationships_never_self_pair_even_with_duplicate_rival_rows`) — 백엔드 테스트 총
  86개로 증가.
- CDP로 전체 플로우(회원가입 → 도시 이름 짓기 → 게임 화면 → HUD/서랍/메뉴 4개 탭 → 영토 구매 → 도시
  건설 → 세계 정세) 끝까지 재검증 완료.

## 라이벌 성향 + 라이벌 자체 도시 확장 (2026-09-22, 이어서)

"관찰의 재미를 늘리자"는 방향으로 두 가지를 추가 제안했고 사용자가 둘 다 채택: (1) 라이벌 국가별
성향 부여 (2) 라이벌도 스스로 수도 외 도시를 짓게 하기. 원래 CLAUDE.md 맨 위 한 줄 요약에 있던
"다른 국가들도 각자 성향에 따라 완전 자율로 발전한다"가 실제로는 구현이 안 돼 있던 부분 — 이번에 채움.

- **라이벌 성향(personality)**: `app/data/rivals.py`에 라이벌마다 고정 성향 배정 — 동쪽 부족 연맹=
  호전적(`aggressive`), 북방 왕국=경제 중심(`economic`), 남방 도시국가=고립주의(`isolationist`).
  `PERSONALITY_TRAITS` 딕셔너리가 성향별로 5가지 배수(`aggression_multiplier`,
  `expansion_multiplier`, `world_war_multiplier`, `alliance_multiplier`,
  `city_founding_multiplier`)를 정의 — 기존 확률 상수들은 그대로 두고 성향이 그 위에 곱해지는
  방식이라, 라이벌 스탯(경제력 기반 확장, 상대 군사력 기반 침략 등)이 여전히 핵심 동력이고 성향은
  "그 위에 얹는 성격"으로만 작동함. `RivalNation`에 `personality` 컬럼 추가, `to_dict()`에 포함.
  적용된 곳: `diplomacy_service.advance_rivals`의 선제 선전포고 확률, `advance_world`의 라이벌간
  전쟁/동맹 확률(양쪽 성향의 평균), `session_manager._resolve_territory_changes`의 영토 확장 확률과
  도시 건설 확률. `DiplomacyPanel.vue`에 성향 배지 표시(⚔️호전적/💰경제 중심/🛡️고립주의).
- **라이벌 자체 도시 건설**: 그동안 도시 설립은 플레이어 전용 기능이라 라이벌은 영원히 수도 하나뿐인
  비대칭이 있었음(영토 구매·인구 상한·멸망은 전부 플레이어·라이벌 동일 규칙이었는데 이것만 예외).
  `models/city.py`에 `owner` 컬럼 추가(`"player"` 또는 라이벌의 rival_id, 기존 행은 전부
  `"player"`로 마이그레이션). `city_service.found_rival_city()`가 플레이어의 `found_city()`와
  같은 거리 규칙(수도/다른 도시와 체비쇼프 거리 3칸 이상)을 그대로 쓰되 무료이고 위치를 라이벌이
  직접 무작위로 고름. 트리거 조건: 보유 타일 `RIVAL_CITY_MIN_TILES=20`개 이상 + 기존 추가 도시
  `RIVAL_CITY_MAX_EXTRA_CITIES=2`개 미만 + 매달 `RIVAL_CITY_BASE_CHANCE_PER_MONTH=0.03 * 성향 배수`
  확률. `session_manager._resolve_territory_changes`가 매달 라이벌마다 검사하고, 성공하면
  `cities_updated` 브로드캐스트 + 게임 로그에 기록. `MapCanvas.vue`는 도시를 그릴 때 이제 무조건
  플레이어 색이 아니라 `owner`에 맞는 색(플레이어=파랑, 라이벌=해당 라이벌 고유색)으로 렌더링.
- 기존 dev DB에 이미 있던 `personality`/`owner` 컬럼은 Alembic 마이그레이션으로 추가 후, 기존
  라이벌 행에 대해 rival_id 기준으로 직접 백필(그냥 `server_default`만 믿으면 전부 같은 성향이
  됐을 것 — 새 컬럼 추가 시 기존 데이터를 의미있게 채우는 건 마이그레이션과 별개의 수동 단계로
  항상 챙길 것).
- 테스트 9개 추가(성향 배정/배수 적용 2개, `found_rival_city` 3개, `_resolve_territory_changes`의
  라이벌 도시 건설·상한 2개 등) — 백엔드 테스트 총 95개. CDP로 세 라이벌의 성향 배지가 화면에 정확히
  표시되는 것까지 확인.

## 자잘한 업그레이드 모음 (2026-09-22, 이어서)

"추가하고 업그레이드 할 거 있으면 다 해줘"라는 포괄적 요청에 4가지를 골라서 처리. 전부 무료
오픈소스/기존 인프라만 사용(유료 서비스 추가 없음).

- **WebSocket 자동 재연결**: `stores/clock.js`가 그동안 연결이 끊겨도(백엔드 재시작, 네트워크 순단 등)
  아무 반응 없이 그냥 멈춰 있었음 — 오래 켜두는 게임 특성상 눈에 안 띄는 채로 "게임이 멈춘 것처럼"
  보일 수 있는 실제 견고성 문제였음. `ws.onclose`에서 지수 백오프(1초→최대 15초)로 재연결 시도,
  `this.socket !== ws` 체크로 의도적 `disconnect()`(로그아웃 등)와 예기치 않은 끊김을 구분해서
  의도적 종료는 재연결 안 함. `ClockPanel.vue`에 "● 재연결 중..." 표시 추가(깜빡이는 애니메이션)로
  플레이어가 지금 무슨 일이 일어나는지 알 수 있게 함.
- **GitHub Actions CI**: `.github/workflows/backend-tests.yml` 추가 — `backend/` 변경이 포함된
  push/PR마다 자동으로 pytest 전체 실행. 격리된 테스트 DB만 쓰므로 완전히 안전.
- **라이벌끼리의 전쟁도 이제 영토가 움직임 + 서로 멸망 가능**: 그동안 "세계 정세"의 라이벌간 전쟁은
  스탯 피해만 주고 영토는 그대로였음(의도적 단순화로 문서화해뒀던 부분). `diplomacy_service.
  advance_world()`가 이제 `(news, world_war_outcomes)`를 반환 — `world_war_outcomes`는 그 달에
  전투가 벌어진 라이벌 쌍마다 (승자, 패자, 승자 이름, 패자 이름) 튜플. `session_manager.
  _resolve_territory_changes`가 이걸 받아서 플레이어-라이벌 전쟁과 완전히 같은 방식으로
  `territory_service.capture_tile(..., allow_elimination=True)`를 호출 — 국경이 실제로 맞닿아
  있어야만 침략 가능하다는 규칙, 최후의 저항 시 멸망 가능하다는 규칙 모두 동일하게 적용됨(플레이어만
  예외적으로 멸망 안 하는 규칙은 그대로 — 라이벌끼리는 둘 다 멸망 가능).
- **동맹의 상호방위**: 동맹이 "그냥 플레이버"였던 걸 실제로 의미 있게 만듦. 플레이어가 어떤 라이벌과
  전쟁 중이고, 그 라이벌에게 동맹국이 있으면, 그 동맹국도 매달 성향에 따라 스케일되는 확률
  (`MUTUAL_DEFENSE_CHANCE_PER_MONTH=0.15 * aggression_multiplier`, 최대 40%)로 참전할 수 있음
  — `diplomacy_service.advance_rivals`에서 매달 라이벌간 동맹 관계를 조회해서 확인. 기존 "무작위
  선제 선전포고" 확률과는 별개 경로(동맹 참전이 먼저 체크되고, 안 걸리면 기존 기회주의적 침략 확률로
  넘어감).
- 테스트 6개 추가(라이벌간 전투 결과 반환, 상호방위 발동/미발동, 세션 매니저의 라이벌간 영토 침략
  처리) — 백엔드 테스트 총 99개. 실제 오래 플레이한 세션(`max12max`)에 30개월치 전체 파이프라인을
  직접 돌려서 크래시 없이 통과하는 것 확인, 그 와중에 실제로 라이벌 하나가 동맹을 맺는 것도 게임
  로그에서 확인됨.

## 테크트리 확장 + 맵 다양성 + 자원 시스템 (2026-09-22, 이어서)

"연구 테크트리 전부 다 만들어도 될듯" + "맵도 매번 다르게, 자원도 다양하게 해서 도시 위치에 이점이
있게" 두 가지 요청을 함께 처리.

- **테크트리 6→20개 확장**: `tech_service.py`의 `TECH_TREE`에 14개 신규 노드 추가(기존 6개는
  id/cost/duration/effects 전부 그대로 — 기존 세이브의 `researched_techs`가 콤마로 이어붙인 id
  문자열이라 절대 안 바뀌어야 함). 경제/군사/학문 세 갈래가 서로 교차 선행조건으로 얽히는 4단계
  구조: 2단계(`currency`/`horseback_riding`/`astronomy`, 각 1단계 기술 하나 선행) → 3단계
  (`philosophy`/`road_network`/`fortification`/`bureaucracy`/`trade_routes`/`cavalry_tactics`,
  일부는 선행 2개 필요) → 4단계(`university`/`banking`/`steel_weapons`/`printing_press`/
  `gunpowder`, 비용 4200~5600·연구기간 14~16개월로 가장 비쌈). 검증 테스트 5개 추가: 중복 id 없음,
  모든 prereq가 실제 존재하는 id를 가리키는지, 사이클이 없는지(위상 정렬 가능), 기존 6개가
  바이트 단위로 안 바뀌었는지, `agriculture→...→banking` 8단계 체인이 실제로 끝까지 연구되는지.
  프론트 `TechPanel.vue`는 코드 수정 없이 그대로 20개를 스크롤 리스트로 렌더링(CDP로 확인) —
  다만 이 시점부터 "10개 넘으면 그래프 UI로 전환" 기준을 넘었으므로, 다음에 테크트리 UI 자체를
  만질 일이 있으면 문명 스타일 노드+연결선 그래프 전환을 먼저 고려할 것(TODO, 이번엔 범위 밖이라
  안 건드림).
- **맵 프리셋(지형 다양성)**: 그동안 `map_service._generate_map`이 물/산/숲/사막 클러스터 파라미터가
  완전히 고정이라 매판 "느낌"이 똑같았음. `MAP_PRESETS` 5종(balanced/archipelago/highlands/arid/
  woodlands, 각각 지형별 시드 개수·크기만 다름) 중 새 세션마다 `random.choice`로 하나 골라 사용.
  기존 `_grow_cluster` 알고리즘 자체는 그대로, 파라미터만 프리셋에서 읽어옴.
- **수도 위치 랜덤화**: 그동안 플레이어 수도가 항상 정확히 `(width//2, height//2)`였음(라이벌 3곳은
  이미 랜덤 밴드였는데 플레이어만 예외). 이제 `_pick_capital_position`이 중앙 안전지대
  (`CAPITAL_X_FRAC_RANGE`/`CAPITAL_Y_FRAC_RANGE` = 0.35~0.65)에서 무작위로 뽑되, 라이벌 수도들과
  체비쇼프 거리 `MIN_CAPITAL_RIVAL_DISTANCE=4` 이상 떨어질 때까지 최대 30회 재시도(둘 다 3x3 블록이라
  4칸 이상이면 절대 안 겹침) — 라이벌 배치를 먼저 하고 그 결과를 알고 나서 플레이어 수도를 고르는
  순서로 바꿈. `test_map_service.py`의 기존 "수도는 항상 정중앙" 테스트를 "수도는 안전지대 안,
  라이벌과 최소 거리 이상"으로 교체.
- **자원 시스템**: `RESOURCE_TYPES` 7종 — 금광/철광(산, 경제/군사), 비옥한 토양/말(평원, 식량/군사),
  목재(숲, 경제), 향신료(사막, 경제), 어장(물, 식량). 지형이 일치하는 타일마다
  `RESOURCE_CHANCE_PER_TILE=5%` 확률로 배치(`_place_resources`), 수도/라이벌 수도 타일 자체는
  제외(도시 아이콘과 안 겹치게). 맵 데이터에 `resources: [{x,y,type}]`로 포함, `/map` 엔드포인트가
  그대로 프론트에 전달. **효과 적용**: `session_manager._compute_resource_bonus`가 수도 + 플레이어가
  세운 모든 도시 기준 반경 1칸 안의 자원을 전부 합산해서 `{economy, military, food}` 보너스 딕셔너리를
  만들고, `advance_nation`이 매달 이걸 기존 랜덤 변동(-4~6)/식량 생산 공식에 그대로 더함 — 즉 "도시를
  어디에 짓느냐"가 매달 실질적인 스탯 차이를 만듦(사용자가 원한 "위치의 이점을 보고 도시를 짓는" 문명식
  플레이 반영). 라이벌은 이 보너스를 받지 않음(라이벌 스탯은 타일 단위가 아니라 국가 전체 집계값 하나라
  자연스럽게 적용 불가 — 기존에 이미 문서화된 "라이벌은 단순화" 패턴과 동일 선상).
- **프론트**: `stores/map.js`가 `resources` 배열과 `resourcesNear(x,y,radius)` 헬퍼를 들고 옴.
  `MapCanvas.vue`가 지형 위에 자원 이모지를 그리고(`RESOURCE_META`, 백엔드 `RESOURCE_TYPES`와 이름/
  아이콘만 미러링), 도시 건설 팝업에 "인근 자원: 🌾 비옥한 토양" 같은 목록을 추가해 클릭한 타일
  주변에 뭐가 있는지 미리 보여줌(자원이 없으면 "인근에 자원이 없습니다").
- **회귀로 깨진 테스트 수정**: `test_api_smoke.py`의 도시 설립 스모크 테스트가 "수도에서 동/서/남/북
  5칸"이라는 고정 오프셋으로 목표 타일을 정하고 있었는데, 수도 위치와 지형이 이제 랜덤이라 그 경로가
  물에 막히거나 라이벌 영토를 가로지를 수 있게 됨 — BFS로 수도에서 도달 가능한(물 아님, 남의 영토
  아님) 가장 가까운 "체비쇼프 거리 3 이상" 타일을 찾아 그 경로를 따라 구매하도록 재작성(구매 대상
  타일 중 이미 소유한 건 건너뜀). 5회 반복 실행으로 안정성 확인.
- 백엔드 테스트 총 111개(신규: 테크트리 무결성/체인 5개, 맵 프리셋·수도 랜덤화·자원 배치 5개, 자원
  보너스 계산 4개). CDP로 테크 패널 20개 노드 렌더링, 랜덤 프리셋/수도 위치 여러 세션에서 확인,
  자원 타일이 지도에 그려지는 것과 도시 건설 팝업의 "인근 자원" 표시까지 실제 화면으로 검증 완료.

## 작업 방식

- 한 단계 끝날 때마다 실제로 서버 띄우고 브라우저에서 확인한 다음 다음 단계로 넘어간다.
- 큰 리팩토링이나 구조 변경이 필요하면 먼저 사용자에게 이유를 설명하고 진행한다.
- 새 패키지를 추가할 때는 `requirements.txt` / `package.json`에 반영하고 어떤 목적인지 간단히 언급한다.
