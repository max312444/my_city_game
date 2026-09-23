"""Game-start difficulty: chosen once per new nation (see NationNamePrompt.vue /
POST .../nation/name), stored on Nation.difficulty. Purely a set of multipliers on
top of the rivals' existing behavior — it never touches the player's own numbers,
same "advisor, not a stat cheat" principle as the rest of the game. Independent
module (no imports of app.services.*) so both diplomacy_service and nation_service
can read it without risking a circular import.
"""

DIFFICULTY_IDS = ["easy", "normal", "hard", "hell"]
DEFAULT_DIFFICULTY = "normal"

DIFFICULTY_META = {
    "easy": {"label": "이지", "description": "라이벌이 느리게 성장하고 좀처럼 먼저 싸움을 걸지 않습니다."},
    "normal": {"label": "노말", "description": "기본 난이도입니다."},
    "hard": {"label": "하드", "description": "라이벌이 빠르게 성장하고 자주 영토를 넓히며 전쟁도 잦아집니다."},
    "hell": {"label": "헬", "description": "라이벌이 훨씬 빠르게 성장하고 공격적으로 확장하며 자주 선전포고합니다."},
}

# rival_growth: multiplies rivals' own monthly economy/military/stability growth.
# aggression: multiplies both the base chance and the cap of a rival striking first.
# expansion: multiplies both the base chance and the cap of a rival claiming a new tile.
DIFFICULTY_MULTIPLIERS = {
    "easy": {"rival_growth": 0.7, "aggression": 0.5, "expansion": 0.7},
    "normal": {"rival_growth": 1.0, "aggression": 1.0, "expansion": 1.0},
    "hard": {"rival_growth": 1.3, "aggression": 1.5, "expansion": 1.3},
    "hell": {"rival_growth": 1.7, "aggression": 2.2, "expansion": 1.6},
}


def difficulty_multiplier(difficulty: str, key: str) -> float:
    return DIFFICULTY_MULTIPLIERS.get(difficulty, DIFFICULTY_MULTIPLIERS[DEFAULT_DIFFICULTY])[key]
