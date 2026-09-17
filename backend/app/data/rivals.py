"""Static rival-nation data shared by diplomacy_service (stats/combat) and
map_service (capital placement). Lives here, independent of both, so neither
service has to import the other just to reach this list — that mutual need was
the root cause of the circular-import workarounds this project kept needing."""

RIVAL_TEMPLATES = [
    {"rival_id": "eastern_tribes", "name": "동쪽 부족 연맹", "economy": 8.0, "stability": 10.0, "military": 14.0},
    {"rival_id": "northern_kingdom", "name": "북방 왕국", "economy": 14.0, "stability": 9.0, "military": 9.0},
    {"rival_id": "southern_city_state", "name": "남방 도시국가", "economy": 12.0, "stability": 14.0, "military": 6.0},
]
