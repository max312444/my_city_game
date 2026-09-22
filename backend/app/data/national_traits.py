"""National traits: a random per-nation specialization (independent of a rival's
personality, which drives diplomatic *behavior* — this drives stat *growth*). Applies
to the player's own nation too, assigned randomly at creation, same as rivals — this
is what makes "우리 나라는 군사 특화" a real, visible thing instead of just flavor text.

Each trait multiplies the *positive* part of a stat's monthly growth delta (same
"only boost growth, never soften a loss" rule as diminishing returns) — one stat gets
a strong boost, the rest are traded off a little so no trait is strictly best."""

NATIONAL_TRAITS = {
    "military": {
        "label": "군사 특화",
        "icon": "⚔️",
        "growth": {"military": 1.6, "economy": 0.85, "stability": 1.0, "education": 0.85},
    },
    "economic": {
        "label": "경제 특화",
        "icon": "💰",
        "growth": {"military": 0.8, "economy": 1.6, "stability": 1.0, "education": 0.9},
    },
    "production": {
        "label": "생산 특화",
        "icon": "🏭",
        "growth": {"military": 0.85, "economy": 1.25, "stability": 1.2, "education": 0.85},
    },
    "scholarly": {
        "label": "학문 특화",
        "icon": "📚",
        "growth": {"military": 0.85, "economy": 0.9, "stability": 1.0, "education": 1.6},
    },
}

NATIONAL_TRAIT_IDS = list(NATIONAL_TRAITS.keys())
