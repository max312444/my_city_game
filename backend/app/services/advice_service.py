import random

ADVICE_CARDS = [
    {
        "id": "tax_policy",
        "title": "세금 정책을 정비해야 합니다",
        "description": "재정 담당관이 세금 제도 개편을 제안합니다. 어떻게 하시겠습니까?",
        "choices": [
            {
                "id": "raise_tax",
                "label": "세금을 인상한다",
                "effects": {"economy": 6, "stability": -4},
            },
            {
                "id": "cut_tax",
                "label": "세금을 인하한다",
                "effects": {"economy": -4, "stability": 6},
            },
            {
                "id": "keep_tax",
                "label": "현행을 유지한다",
                "effects": {"economy": 0, "stability": 0},
            },
        ],
    },
    {
        "id": "military_budget",
        "title": "국방 예산 편성 시기입니다",
        "description": "군부에서 예산 증액을 요청하고 있습니다.",
        "choices": [
            {
                "id": "boost_military",
                "label": "국방 예산을 늘린다",
                "effects": {"military": 6, "economy": -3},
            },
            {
                "id": "cut_military",
                "label": "국방 예산을 줄이고 복지에 투자한다",
                "effects": {"military": -4, "stability": 5},
            },
            {
                "id": "keep_military",
                "label": "현행 예산을 유지한다",
                "effects": {"military": 0},
            },
        ],
    },
    {
        "id": "education_reform",
        "title": "교육 제도 개혁안이 올라왔습니다",
        "description": "교육부에서 새로운 개혁안을 검토해달라고 요청합니다.",
        "choices": [
            {
                "id": "invest_education",
                "label": "교육에 대규모 투자를 한다",
                "effects": {"education": 6, "economy": -3},
            },
            {
                "id": "minor_reform",
                "label": "소규모 개선만 진행한다",
                "effects": {"education": 3, "economy": -1},
            },
            {
                "id": "skip_reform",
                "label": "개혁을 보류한다",
                "effects": {"education": -3, "stability": 2},
            },
        ],
    },
]


def get_random_advice() -> dict:
    return random.choice(ADVICE_CARDS)
