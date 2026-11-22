"""Synthetic crew and maintenance data for planted-cause worlds.

The real BTS flights and the real weather stay fixed. This module writes the
two divisions we have no public data for, so that the true internal cause of a
disruption is known by construction.

Two dials set the world:
  crew_effect         share of the real excess idle aircraft explained by crews
  maintenance_effect  share explained by maintenance
The dials must sum to 1 or less. Whatever is left over is unexplained, which is
the "neither" world when both are 0.

Design rules (see the spec, "Synthetic divisions"):
  * Only measurable quantities are written (rosters, availability, reserve use,
    duty hours, aircraft out of service, open defects). No "shortage" flag.
  * The true cause is returned separately as ground truth and never written
    into a table.
  * Every number that is an assumption lives in ASSUMPTIONS and is made up.
  * A fixed seed makes a world reproducible. Normal crew noise, normal
    maintenance noise and the planted effect each use their own random stream,
    so two worlds differ only in the numbers the planted cause touches.

Calibration note: the size of the planted effect is scaled to the real excess
idleness (baseline aircraft flying minus aircraft flying that day) so the world
is consistent with the real data. The planted cause is the dial setting; the
excess idleness itself is a real consequence.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

# Made-up modeling assumptions, not measured or sourced values.
ASSUMPTIONS = {
    "legs_per_crew_day": 3,          # flights one crew operates in a day
    "reserve_ratio": 0.12,           # reserve crews as a share of the roster
    "base_out_rate": 0.04,           # crews unavailable on a normal day
    "crews_per_aircraft_day": 2.0,   # crews tied to one aircraft-day of flying
    "base_duty_hours": 8.0,          # average duty hours on a normal day
    "duty_stretch_hours": 3.0,       # extra hours when reserves are fully drawn
    "base_oos_rate": 0.02,           # share of fleet out of service normally
    "defects_per_oos_aircraft": 2.5,
    "base_defect_rate": 0.10,        # normal open defects per aircraft
}


@dataclass(frozen=True)
class World:
    name: str
    crew_effect: float = 0.0
    maintenance_effect: float = 0.0
    seed: int = 0

    def __post_init__(self):
        for v in (self.crew_effect, self.maintenance_effect):
            if not 0.0 <= v <= 1.0:
                raise ValueError("dials must be between 0 and 1")
        if self.crew_effect + self.maintenance_effect > 1.0 + 1e-9:
            raise ValueError("crew_effect + maintenance_effect must be 1 or less")

    def ground_truth(self) -> dict:
        causes = []
        if self.crew_effect > 0:
            causes.append("crew")
        if self.maintenance_effect > 0:
            causes.append("maintenance")
        return {
            "world": self.name,
            "crew_effect": self.crew_effect,
            "maintenance_effect": self.maintenance_effect,
            "true_internal_causes": causes or ["none"],
            "seed": self.seed,
        }


WORLDS = {
    "crew": World("crew", crew_effect=1.0),
    "maintenance": World("maintenance", maintenance_effect=1.0),
    "neither": World("neither"),
    "mixed": World("mixed", crew_effect=0.5, maintenance_effect=0.5),
}


def _excess_idle(flights, baseline, event):
    """Per day: baseline aircraft flying minus aircraft flying (0 outside the event)."""
    flown = flights[flights["cancelled"] == 0]
    tails = flown.groupby("flight_date")["tail_number"].nunique()
    days = sorted(flights["flight_date"].unique())
    tails = tails.reindex(days).fillna(0)
    b0, b1 = baseline
    base = tails[(tails.index >= b0) & (tails.index <= b1)].median()
    excess = (base - tails).clip(lower=0)
    if event is None:
        return excess * 0
    e0, e1 = event
    return excess.where((excess.index >= e0) & (excess.index <= e1), 0)


def generate(flights, world, baseline, event=None, assumptions=None):
    """Return (crew_daily, maintenance_daily, ground_truth).

    flights   DataFrame with flight_date, origin, tail_number, cancelled
    baseline  (first_day, last_day) of normal days, used to size rosters
    event     (first_day, last_day) where the planted cause acts, or None
    Dates must be comparable (e.g. datetime.date objects).
    """
    a = {**ASSUMPTIONS, **(assumptions or {})}
    noise_crew = np.random.default_rng([world.seed, 1])
    noise_maint = np.random.default_rng([world.seed, 2])
    effect = np.random.default_rng([world.seed, 3])
    excess = _excess_idle(flights, baseline, event)
    days = list(excess.index)

    # Crew: departures scheduled per base per day (cancelled flights included).
    dep = (flights.groupby(["flight_date", "origin"]).size()
           .unstack(fill_value=0).reindex(days, fill_value=0))
    needed = np.ceil(dep / a["legs_per_crew_day"]).astype(int)

    b0, b1 = baseline
    base_needed = needed[(needed.index >= b0) & (needed.index <= b1)].median()
    base_needed = base_needed.where(base_needed > 0, needed.max())
    roster = np.ceil(base_needed * (1 + a["reserve_ratio"])).astype(int)
    reserve = np.ceil(roster * a["reserve_ratio"] / (1 + a["reserve_ratio"])).astype(int)
    regular = roster - reserve
    share = (roster / roster.sum()).to_numpy()

    rows = []
    for day in days:
        extra_total = int(round(world.crew_effect * excess[day]
                                * a["crews_per_aircraft_day"]))
        extra = effect.multinomial(extra_total, share) if extra_total > 0 \
            else np.zeros(len(roster), dtype=int)
        for i, base in enumerate(roster.index):
            r, rs, rg = int(roster[base]), int(reserve[base]), int(regular[base])
            out = min(r, int(noise_crew.binomial(r, a["base_out_rate"])) + int(extra[i]))
            reg_out = min(rg, int(round(out * rg / r)))
            res_out = min(rs, out - reg_out)
            reg_av, res_av = rg - reg_out, rs - res_out
            need = int(needed.loc[day, base])
            used = int(np.clip(need - reg_av, 0, res_av))
            duty = (a["base_duty_hours"]
                    + a["duty_stretch_hours"] * used / max(rs, 1)
                    + noise_crew.normal(0, 0.25))
            rows.append((day, base, int(dep.loc[day, base]), need, r, rs,
                         reg_av + res_av, used, round(float(duty), 2)))
    crew = pd.DataFrame(rows, columns=[
        "day", "base", "departures", "crews_needed", "crews_rostered",
        "reserve_pool", "crews_available", "reserve_used", "avg_duty_hours"])

    # Maintenance: fleet-level per day.
    fleet = int(flights["tail_number"].nunique())
    rows = []
    for day in days:
        oos = int(noise_maint.poisson(a["base_oos_rate"] * fleet)
                  + round(world.maintenance_effect * excess[day]))
        defects = int(noise_maint.poisson(a["defects_per_oos_aircraft"] * oos
                                  + a["base_defect_rate"] * fleet))
        rows.append((day, fleet, oos, defects))
    maint = pd.DataFrame(rows, columns=[
        "day", "fleet_size", "aircraft_out_of_service", "open_defects"])
    return crew, maint, world.ground_truth()
