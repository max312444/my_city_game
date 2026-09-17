# Regnum

> 그대는 왕이 아니다. 왕의 곁을 지키는 조언자일 뿐.

문명(Civilization)류 국가 운영 게임을 "조언자" 시점으로 다시 만들어본 프로젝트입니다. 플레이어는 나라를
직접 통치하지 않습니다 — 국가는 경제/외교/전쟁을 전부 AI가 자동으로 판단해서 운영하고, 플레이어는 몇 분에
한 번씩 오는 조언 카드를 클릭해서 방향만 살짝 유도할 수 있습니다. 승패 조건은 없습니다.

## 핵심 루프

1. 게임 시계가 흐르며 매달 국가 지표(경제력/안정도/군사력/교육/인구/식량/치안)가 자동으로 변화합니다.
2. 주기적으로 AI가 현재 국가 상황에 맞는 조언 카드 3개를 제시합니다. 선택은 플레이어 몫이지만, 효과는
   크지 않습니다 — 조언자일 뿐이니까요.
3. 그 사이 국가는 스스로 테크를 연구하고, 위인이 등장하고, 이웃 나라와 전쟁·평화·동맹을 오가고, 영토를
   사고 빼앗기기도 합니다. 플레이어는 이걸 지켜보고, 가끔 개입합니다.

## 주요 기능

- **국가 시뮬레이션**: 경제/안정도/군사력/교육 + 인구·식량(문명 스타일) + 국고/파산 시스템, 스탯이
  상한에 가까워질수록 성장이 둔화되는 디미니싱 리턴 적용
- **테크트리**: 선행조건 그래프 + 실제 시간이 걸리는 연구(즉시 완료 아님)
- **위인 시스템**: 경제/군사/학문/정치 4개 분야, 세이브당 중복 등장 없음, 플레이어가 소환하지 않고
  자동으로 등장
- **빅 이벤트**: 가뭄/전염병/화재 같은 악재와 풍작/유전 발견 같은 호재가 낮은 확률로 발생
- **외교 & 전쟁**: 고정 AI 라이벌 3개국과 선전포고/평화 제안, 전쟁이 길어지면 자동으로 지쳐서 끝나기도
  하고, 라이벌이 먼저 선전포고하기도 함. 라이벌끼리도 플레이어와 무관하게 전쟁/동맹을 맺음. 전쟁에서
  패배가 누적되면 라이벌 국가가 멸망할 수도 있음(플레이어는 예외)
- **절차적 지도**: Canvas 2D로 그린 지형(이미지 에셋 없음), 문명처럼 돈으로 인접 타일을 사서 영토를
  넓히는 방식, 수도 외 추가 도시 건설 가능
- **계정 시스템**: 아이디/비밀번호 회원가입·로그인(PBKDF2 해싱), 로그인 세션은 새로고침해도 유지됨

## 기술 스택

**백엔드**: Python + FastAPI(비동기), SQLAlchemy 2.0 async + SQLite, Alembic 마이그레이션, 네이티브
FastAPI WebSocket, Anthropic API(조언 카드 생성, 실패 시 하드코딩 폴백)

**프론트엔드**: Vue 3(Composition API) + Vite, Pinia, Canvas 2D 지도 렌더링, 네이티브 WebSocket

인프라는 의도적으로 가볍게 유지합니다 — Redis/Celery/PostgreSQL 같은 건 필요해지기 전까진 안 씁니다.

## 시작하기

### 백엔드

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows (macOS/Linux는 source venv/bin/activate)
pip install -r requirements.txt

cp .env.example .env           # ANTHROPIC_API_KEY 채워넣기 (없어도 하드코딩 조언으로 폴백됨)

alembic upgrade head           # DB 스키마 최신화
uvicorn app.main:app --reload --port 8000
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

백엔드(8000)와 프론트엔드(5173)를 둘 다 띄운 상태에서 브라우저로 `localhost:5173`에 접속하면 됩니다.

### 테스트

```bash
cd backend
pytest                         # 격리된 테스트 DB에서 실행, 실제 세이브 파일은 건드리지 않음
```

## 스키마를 바꿀 때

수동으로 `ALTER TABLE`을 하지 말고 항상 Alembic을 통해서 바꿉니다.

```bash
# 1. backend/app/models/*.py 에서 모델 수정
# 2. (새 모델 파일을 추가했다면 alembic/env.py의 import 목록에도 추가할 것!)
alembic revision --autogenerate -m "설명"
# 3. 생성된 마이그레이션 파일 검토 (SQLite는 컬럼 추가 시 server_default 필수)
alembic upgrade head
```

## 프로젝트 구조

```
backend/
├── app/
│   ├── main.py              # FastAPI 앱, REST/WebSocket 엔드포인트
│   ├── core/                # 게임 시계, 세션 오케스트레이션
│   ├── models/               # SQLAlchemy 모델
│   ├── services/             # 국가/테크/외교/영토/맵/인증 등 핵심 로직
│   └── data/                  # 순수 정적 데이터 (라이벌 국가 템플릿 등)
├── alembic/                  # DB 마이그레이션
└── tests/                    # pytest (격리된 DB, 62+개 테스트)

frontend/
└── src/
    ├── components/            # MapCanvas, TopHud, GameMenu, DiplomacyPanel 등
    └── stores/                 # Pinia 스토어 (세션당 하나씩)
```

## 더 자세한 내용

설계 결정, 밸런스 튜닝 이력, 알려진 제약사항, 다음에 할 일은 [CLAUDE.md](CLAUDE.md)에 시간순으로
정리되어 있습니다.
