from app.core import session_manager
from app.services import map_service, nation_service, territory_service


async def test_resolve_territory_changes_no_war_no_capture(session_id):
    await nation_service.get_or_create_nation(session_id)
    map_data = await map_service.get_or_create_map(session_id)
    rivals = [{"rival_id": rc["rival_id"], "economy": 0.0} for rc in map_data["rival_capitals"]]

    reports, changed = await session_manager._resolve_territory_changes(session_id, rivals, [])
    assert reports == []
    assert changed is False  # 0 economy -> 0% expansion chance, and no war outcomes to resolve


async def test_resolve_territory_changes_reports_and_broadcasts_capture(session_id):
    # Seed the player and a rival touching borders *before* get_or_create_map ever runs
    # for this session — its own (idempotent) seeding step will then leave these custom
    # positions alone, since ensure_initial_territory/ensure_rival_territory both no-op
    # once an owner already has tiles.
    await nation_service.get_or_create_nation(session_id)
    await territory_service.ensure_initial_territory(session_id, 10, 10)  # owns x:9-11,y:9-11
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)  # owns x:12-14,y:9-11

    war_outcomes = [("player", "eastern_tribes", "테스트라이벌")]
    reports, changed = await session_manager._resolve_territory_changes(session_id, [], war_outcomes)

    assert changed is True
    assert any("테스트라이벌" in r and "점령" in r for r in reports)
