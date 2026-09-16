import os
import uuid

from anthropic import AsyncAnthropic

from app.services.advice_service import get_random_advice

MODEL = "claude-haiku-4-5-20251001"

ADVICE_TOOL = {
    "name": "create_advice_card",
    "description": "국가 상태에 맞는 정책 조언 카드를 하나 생성한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "조언 카드 제목 (한 문장, 한국어)"},
            "description": {
                "type": "string",
                "description": "상황 설명 (한두 문장, 한국어)",
            },
            "choices": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "선택지 문구 (한국어)"},
                        "effects": {
                            "type": "object",
                            "description": "이 선택을 골랐을 때 국가 지표 변화량 (-200~200 정수, 지표는 0~1000 범위)",
                            "properties": {
                                "economy": {"type": "integer"},
                                "stability": {"type": "integer"},
                                "military": {"type": "integer"},
                                "education": {"type": "integer"},
                            },
                        },
                    },
                    "required": ["label", "effects"],
                },
            },
        },
        "required": ["title", "description", "choices"],
    },
}

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic | None:
    global _client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    if _client is None:
        _client = AsyncAnthropic(api_key=api_key)
    return _client


def _clamp_effects(effects: dict) -> dict:
    clamped = {}
    for stat in ("economy", "stability", "military", "education"):
        if stat in effects:
            clamped[stat] = max(-200, min(200, int(effects[stat])))
    return clamped


def _build_prompt(nation: dict, current_date: dict) -> str:
    return (
        f"현재 시점: {current_date['year']}년 {current_date['month']}월\n"
        f"국가 상태 (각 지표는 0~1000 범위) - 경제력: {nation['economy']}, 안정도: {nation['stability']}, "
        f"군사력: {nation['military']}, 교육: {nation['education']}, 보유 금액: {nation['treasury']}\n\n"
        "이 국가의 군주에게 지금 상황에 맞는 정책 조언 카드를 하나 만들어줘. "
        "선택지 3개는 서로 뚜렷하게 다른 방향(예: 공격적/신중함/현상 유지)이어야 하고, "
        "국가 상태가 특정 지표에서 위태로우면(예: 안정도가 낮으면) 그걸 반영한 상황을 만들어줘."
    )


async def generate_advice(nation: dict, current_date: dict) -> dict:
    client = _get_client()
    if client is None:
        return get_random_advice()

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=[ADVICE_TOOL],
            tool_choice={"type": "tool", "name": "create_advice_card"},
            messages=[{"role": "user", "content": _build_prompt(nation, current_date)}],
        )
        tool_use = next(b for b in response.content if b.type == "tool_use")
        data = tool_use.input

        return {
            "id": f"llm_{uuid.uuid4().hex[:8]}",
            "title": data["title"],
            "description": data["description"],
            "choices": [
                {
                    "id": f"choice_{i}",
                    "label": choice["label"],
                    "effects": _clamp_effects(choice.get("effects", {})),
                }
                for i, choice in enumerate(data["choices"])
            ],
        }
    except Exception:
        return get_random_advice()
