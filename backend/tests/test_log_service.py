from app.services import log_service


async def test_add_log_and_get_logs_oldest_first(session_id):
    await log_service.add_log(session_id, 1, 3, "tech", "농경법 연구를 완료했습니다.")
    await log_service.add_log(session_id, 2, 5, "event", "가뭄: 식량이 줄었습니다.")

    entries = await log_service.get_logs(session_id)
    assert len(entries) == 2
    assert entries[0]["year"] == 1 and entries[0]["category"] == "tech"
    assert entries[1]["year"] == 2 and entries[1]["category"] == "event"


async def test_add_logs_skips_empty_list(session_id):
    await log_service.add_logs(session_id, 1, 1, "war", [])
    assert await log_service.get_logs(session_id) == []


async def test_add_logs_writes_every_message(session_id):
    await log_service.add_logs(session_id, 3, 4, "war", ["첫 번째 전투 결과", "두 번째 전투 결과"])
    entries = await log_service.get_logs(session_id)
    assert [e["message"] for e in entries] == ["첫 번째 전투 결과", "두 번째 전투 결과"]
    assert all(e["category"] == "war" for e in entries)


async def test_delete_logs_removes_everything(session_id):
    await log_service.add_log(session_id, 1, 1, "tech", "메시지")
    await log_service.delete_logs(session_id)
    assert await log_service.get_logs(session_id) == []


async def test_logs_are_isolated_per_session(session_id):
    other_session = session_id + "_other"
    await log_service.add_log(session_id, 1, 1, "tech", "내 로그")
    await log_service.add_log(other_session, 1, 1, "tech", "다른 세션 로그")

    entries = await log_service.get_logs(session_id)
    assert len(entries) == 1
    assert entries[0]["message"] == "내 로그"
