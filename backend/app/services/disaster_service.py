import random

RANDOM_EVENT_CHANCE_PER_MONTH = 0.01

RANDOM_EVENTS = [
    {
        "id": "drought",
        "name": "가뭄",
        "description": "오랜 가뭄으로 농작물이 말라붙어 식량 비축량이 줄었습니다.",
        "positive": False,
        "food_loss_months": 2,
    },
    {
        "id": "plague",
        "name": "전염병",
        "description": "정체불명의 전염병이 퍼져 백성 일부가 목숨을 잃고 민심이 흉흉해졌습니다.",
        "positive": False,
        "population_percent": -0.06,
        "stat_effects": {"stability": -0.1},
    },
    {
        "id": "great_fire",
        "name": "대화재",
        "description": "도심에 화재가 발생해 상업 시설과 재산 일부가 잿더미가 되었습니다.",
        "positive": False,
        "stat_effects": {"economy": -0.12},
        "treasury_loss_months": 2,
    },
    {
        "id": "earthquake",
        "name": "지진",
        "description": "지진이 발생해 건물과 시설 일부가 무너지고 도시가 피해를 입었습니다.",
        "positive": False,
        "stat_effects": {"economy": -0.08, "military": -0.08, "stability": -0.08},
    },
    {
        "id": "flood",
        "name": "홍수",
        "description": "강이 범람해 농경지가 물에 잠기고 상업 활동이 타격을 입었습니다.",
        "positive": False,
        "stat_effects": {"economy": -0.08},
        "food_loss_months": 1.5,
    },
    {
        "id": "bountiful_harvest",
        "name": "풍작",
        "description": "날씨가 좋아 풍작을 이루어 식량 비축량이 늘었습니다.",
        "positive": True,
        "food_loss_months": -1.5,
    },
    {
        "id": "oil_discovery",
        "name": "유전 발견",
        "description": "영토 내에서 유전이 발견되어 국고에 여유가 생겼습니다.",
        "positive": True,
        "treasury_loss_months": -2.5,
        "stat_effects": {"economy": 0.08},
    },
    {
        "id": "relic_discovery",
        "name": "고대 유물 발견",
        "description": "고대 유적에서 귀중한 유물이 발굴되어 학계가 들썩이고 국고 수입도 조금 늘었습니다.",
        "positive": True,
        "treasury_loss_months": -1.5,
        "stat_effects": {"education": 0.08},
    },
    {
        "id": "immigration_wave",
        "name": "이민 행렬",
        "description": "주변에서 이민자들이 들어와 인구가 늘었습니다.",
        "positive": True,
        "population_percent": 0.06,
    },
    {
        "id": "trade_boom",
        "name": "교역 호황",
        "description": "무역로가 번성하며 상업 활동이 활기를 띠었습니다.",
        "positive": True,
        "stat_effects": {"economy": 0.1, "stability": 0.05},
    },
]


def maybe_trigger_event() -> dict | None:
    if random.random() < RANDOM_EVENT_CHANCE_PER_MONTH:
        return random.choice(RANDOM_EVENTS)
    return None
