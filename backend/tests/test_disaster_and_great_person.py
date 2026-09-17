from app.services import disaster_service, great_person_service, nation_service


def test_random_events_each_declare_positive_or_negative():
    for event in disaster_service.RANDOM_EVENTS:
        assert isinstance(event["positive"], bool)


def test_event_chance_is_a_small_probability():
    assert 0 < disaster_service.RANDOM_EVENT_CHANCE_PER_MONTH < 0.1


async def test_great_person_never_repeats_for_the_same_session(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    monkeypatch.setattr(great_person_service.random, "random", lambda: 0.0)  # force a spawn every call

    seen_ids = set()
    for month in range(1, len(great_person_service.GREAT_PEOPLE) + 1):
        nation = await nation_service.get_or_create_nation(session_id)
        nation, person = await great_person_service.maybe_spawn_great_person(
            session_id, nation, {"year": 1, "month": month}
        )
        assert person is not None
        assert person["id"] not in seen_ids
        seen_ids.add(person["id"])

    assert seen_ids == set(great_person_service.GREAT_PEOPLE_BY_ID)


async def test_great_person_spawn_none_once_pool_exhausted(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    monkeypatch.setattr(great_person_service.random, "random", lambda: 0.0)

    nation = await nation_service.get_or_create_nation(session_id)
    for month in range(1, len(great_person_service.GREAT_PEOPLE) + 1):
        nation, _ = await great_person_service.maybe_spawn_great_person(
            session_id, nation, {"year": 1, "month": month}
        )

    nation, person = await great_person_service.maybe_spawn_great_person(
        session_id, nation, {"year": 2, "month": 1}
    )
    assert person is None  # every great person has already appeared this session


async def test_great_person_history_reflects_appearances(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    monkeypatch.setattr(great_person_service.random, "random", lambda: 0.0)

    nation = await nation_service.get_or_create_nation(session_id)
    await great_person_service.maybe_spawn_great_person(session_id, nation, {"year": 3, "month": 5})

    history = await great_person_service.get_history(session_id)
    assert len(history) == 1
    assert history[0]["year"] == 3
    assert history[0]["month"] == 5
