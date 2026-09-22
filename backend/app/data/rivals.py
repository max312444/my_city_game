"""Static rival-nation data shared by diplomacy_service (stats/combat), map_service
(capital placement), and city_service (autonomous rival city founding). Lives here,
independent of all of them, so no service has to import another just to reach this
data — that mutual need was the root cause of the circular-import workarounds this
project kept needing."""

RIVAL_TEMPLATES = [
    {
        "rival_id": "eastern_tribes",
        "name": "동쪽 부족 연맹",
        "economy": 8.0,
        "stability": 10.0,
        "military": 14.0,
        "personality": "aggressive",
    },
    {
        "rival_id": "northern_kingdom",
        "name": "북방 왕국",
        "economy": 14.0,
        "stability": 9.0,
        "military": 9.0,
        "personality": "economic",
    },
    {
        "rival_id": "southern_city_state",
        "name": "남방 도시국가",
        "economy": 12.0,
        "stability": 14.0,
        "military": 6.0,
        "personality": "isolationist",
    },
]

# Personality multipliers layered on top of the existing base chances — a rival's
# stats still drive the underlying math (economy for expansion, relative military
# for aggression), personality just leans that math one way or another so the 3
# fixed rivals actually feel like different characters instead of the same AI with
# different starting numbers.
PERSONALITY_TRAITS = {
    "aggressive": {
        "aggression_multiplier": 2.5,
        "expansion_multiplier": 1.3,
        "world_war_multiplier": 2.0,
        "alliance_multiplier": 0.4,
        "city_founding_multiplier": 0.7,
    },
    "economic": {
        "aggression_multiplier": 0.5,
        "expansion_multiplier": 1.5,
        "world_war_multiplier": 0.5,
        "alliance_multiplier": 1.8,
        "city_founding_multiplier": 1.8,
    },
    "isolationist": {
        "aggression_multiplier": 0.2,
        "expansion_multiplier": 0.7,
        "world_war_multiplier": 0.3,
        "alliance_multiplier": 0.3,
        "city_founding_multiplier": 0.9,
    },
}

PERSONALITY_LABELS = {
    "aggressive": "호전적",
    "economic": "경제 중심",
    "isolationist": "고립주의",
}

RIVAL_CITY_NAME_POOL = ["새터", "변경진", "항구촌", "교역소", "성채", "언덕마을", "강나루", "숲마을"]
