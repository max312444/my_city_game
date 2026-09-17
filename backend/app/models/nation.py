import math
import random

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

INCOME_PER_ECONOMY_POINT = 5
MILITARY_UPKEEP_RATE = 2
EDUCATION_UPKEEP_RATE = 1
STABILITY_UPKEEP_RATE = 0.5
STAT_MAX = 1000.0

INITIAL_POPULATION = 50.0
DEFAULT_LAND_CAPACITY = 1000.0
# A metropolis with dozens of tiles should be able to hold a real city's worth of
# people, not cap out around 2-3k — capacity now scales with how much land the
# player actually owns instead of sitting at one flat number forever.
LAND_CAPACITY_PER_TILE = 500
CITY_ECONOMY_BONUS_PER_CITY = 0.05  # each founded city (beyond the capital) adds this much


def compute_land_capacity(owned_tile_count: int) -> int:
    return max(int(DEFAULT_LAND_CAPACITY), owned_tile_count * LAND_CAPACITY_PER_TILE)

FOOD_PER_CAPITA_PRODUCTION = 0.7
FOOD_PER_CAPITA_CONSUMPTION = 0.6
FOOD_GROWTH_SENSITIVITY = 0.3


def population_factor(population: float) -> float:
    """Bigger population boosts economic/military output. 1.0x at the starting population."""
    return math.sqrt(max(population, 1.0) / INITIAL_POPULATION)


def satisfaction_fraction(stability: float) -> float:
    """0.3-1.0 fraction driven by stability; used for both display and population growth."""
    return 0.3 + 0.7 * (stability / STAT_MAX)


def _initial_stat() -> float:
    return random.uniform(5, 10)


class Nation(Base):
    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="플레이어 국가")
    economy: Mapped[float] = mapped_column(Float, default=_initial_stat)
    stability: Mapped[float] = mapped_column(Float, default=_initial_stat)
    military: Mapped[float] = mapped_column(Float, default=_initial_stat)
    education: Mapped[float] = mapped_column(Float, default=_initial_stat)
    treasury: Mapped[float] = mapped_column(Float, default=0.0)
    year: Mapped[int] = mapped_column(Integer, default=1)
    month: Mapped[int] = mapped_column(Integer, default=1)
    researched_techs: Mapped[str] = mapped_column(String, default="")
    current_research: Mapped[str] = mapped_column(String, default="")
    current_research_months_left: Mapped[int] = mapped_column(Integer, default=0)
    population: Mapped[int] = mapped_column(Integer, default=int(INITIAL_POPULATION))
    population_growth_buffer: Mapped[float] = mapped_column(Float, default=0.0)
    land_capacity: Mapped[int] = mapped_column(Integer, default=int(DEFAULT_LAND_CAPACITY))
    food_stock: Mapped[float] = mapped_column(Float, default=0.0)
    food_bonus: Mapped[float] = mapped_column(Float, default=0.0)

    def to_dict(self):
        pop_factor = population_factor(self.population)
        income = self.economy * INCOME_PER_ECONOMY_POINT * pop_factor
        expenses = (
            self.military * MILITARY_UPKEEP_RATE
            + self.education * EDUCATION_UPKEEP_RATE
            + self.stability * STABILITY_UPKEEP_RATE
        )
        food_production = self.population * (FOOD_PER_CAPITA_PRODUCTION + self.food_bonus)
        food_consumption = self.population * FOOD_PER_CAPITA_CONSUMPTION
        return {
            "name": self.name,
            "economy": round(self.economy, 1),
            "stability": round(self.stability, 1),
            "military": round(self.military, 1),
            "education": round(self.education, 1),
            "monthly_income": round(income, 1),
            "monthly_expenses": round(expenses, 1),
            "monthly_net": round(income - expenses, 1),
            "treasury": round(self.treasury, 1),
            "is_bankrupt": self.treasury < 0,
            "population": self.population,
            "land_capacity": self.land_capacity,
            "population_density": round(self.population / self.land_capacity * 100, 1),
            "satisfaction": round(satisfaction_fraction(self.stability) * 100, 1),
            "food_production": round(food_production, 1),
            "food_consumption": round(food_consumption, 1),
            "food_net": round(food_production - food_consumption, 1),
            "food_stock": round(self.food_stock, 1),
            "is_famine": self.food_stock < 0,
        }
