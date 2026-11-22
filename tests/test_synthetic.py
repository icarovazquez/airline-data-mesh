import datetime as dt
import pandas as pd
import pytest
from airline_mesh.synthetic.generator import World, WORLDS, generate

D = lambda n: dt.date(2022, 12, n)


def make_flights():
    """Two bases, 3 flights each per day, 10 aircraft. Aircraft flying drops on days 6-8."""
    rows = []
    for day in range(1, 11):
        for base in ("AAA", "BBB"):
            for k in range(30):
                tail = f"N{k % 10:03d}"
                idle = day in (6, 7, 8) and (k % 10) < 5
                rows.append((D(day), base, tail, 1.0 if idle else 0.0))
    return pd.DataFrame(rows, columns=["flight_date", "origin", "tail_number", "cancelled"])


BASE = (D(1), D(5))
EVENT = (D(6), D(8))


def run(world, event=EVENT):
    return generate(make_flights(), world, BASE, event)


def test_dials_validated():
    with pytest.raises(ValueError):
        World("bad", crew_effect=0.7, maintenance_effect=0.5)
    with pytest.raises(ValueError):
        World("bad", crew_effect=-0.1)


def test_reproducible_with_seed():
    a = run(World("crew", crew_effect=1.0, seed=3))
    b = run(World("crew", crew_effect=1.0, seed=3))
    pd.testing.assert_frame_equal(a[0], b[0])
    pd.testing.assert_frame_equal(a[1], b[1])


def test_crew_world_depletes_crews_not_maintenance():
    crew, maint, truth = run(WORLDS["crew"])
    ev = crew[crew.day.isin([D(6), D(7), D(8)])]
    ok = crew[crew.day <= D(5)]
    assert ev.crews_available.mean() < ok.crews_available.mean()
    assert ev.reserve_used.mean() > ok.reserve_used.mean()
    assert truth["true_internal_causes"] == ["crew"]
    m_ev = maint[maint.day.isin([D(6), D(7), D(8)])].aircraft_out_of_service.mean()
    m_ok = maint[maint.day <= D(5)].aircraft_out_of_service.mean()
    assert m_ev - m_ok < 2


def test_maintenance_world_grounds_aircraft_not_crews():
    crew, maint, truth = run(WORLDS["maintenance"])
    m_ev = maint[maint.day.isin([D(6), D(7), D(8)])].aircraft_out_of_service.mean()
    m_ok = maint[maint.day <= D(5)].aircraft_out_of_service.mean()
    assert m_ev > m_ok + 3
    ev = crew[crew.day.isin([D(6), D(7), D(8)])]
    ok = crew[crew.day <= D(5)]
    assert abs(ev.crews_available.mean() - ok.crews_available.mean()) < 2
    assert truth["true_internal_causes"] == ["maintenance"]


def test_neither_world_looks_healthy_and_truth_says_none():
    crew, maint, truth = run(WORLDS["neither"])
    assert truth["true_internal_causes"] == ["none"]
    assert maint.aircraft_out_of_service.max() < 4


def test_no_event_means_no_planted_effect():
    crew, maint, _ = run(WORLDS["crew"], event=None)
    assert crew.reserve_used.max() <= crew.reserve_pool.max()
    assert maint.aircraft_out_of_service.max() < 4


def test_tables_carry_no_answer_columns():
    crew, maint, _ = run(WORLDS["mixed"])
    banned = {"shortage", "cause", "world", "crew_effect", "maintenance_effect", "truth"}
    for df in (crew, maint):
        assert not banned & {c.lower() for c in df.columns}
