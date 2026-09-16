class GameClock:
    def __init__(self, real_seconds_per_month_base: float = 6):
        self.base_interval = real_seconds_per_month_base
        self.speed = "normal"  # paused | normal | fast | fastest
        self.accumulated_seconds = 0.0
        self.current_date = {"year": 1, "month": 1}

    def get_interval(self):
        multiplier = {"paused": None, "normal": 1, "fast": 2, "fastest": 4}[self.speed]
        if multiplier is None:
            return None
        return self.base_interval / multiplier

    async def tick(self, delta_seconds: float, on_month_advance):
        interval = self.get_interval()
        if interval is None:
            return
        self.accumulated_seconds += delta_seconds
        while self.accumulated_seconds >= interval:
            self.accumulated_seconds -= interval
            self._advance_one_month()
            await on_month_advance(self.current_date)

    def _advance_one_month(self):
        self.current_date["month"] += 1
        if self.current_date["month"] > 12:
            self.current_date["month"] = 1
            self.current_date["year"] += 1
