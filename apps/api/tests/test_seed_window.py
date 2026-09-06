"""Synthetic fixtures remain usable after their original demonstration date."""

from datetime import date, datetime, timedelta

import pytest


@pytest.mark.parametrize("end_date", [date(2026, 9, 5), date(2027, 1, 3)])
def test_seed_can_anchor_window_without_rewriting_source(
    tmp_path, records_root, monkeypatch, end_date
):
    import seed

    from core.settings import get_settings
    from record.store import get_store

    source = seed.HERE / "residents.json"
    original = source.read_bytes()
    root = tmp_path / "records"
    monkeypatch.setenv("RECORDS_ROOT", str(root))
    get_settings.cache_clear()
    get_store.cache_clear()
    try:
        seeded = seed.seed(root, quiet=True, end_date=end_date)
        for pid in seeded.list_patients():
            wear = seeded.load_timeline(pid, kinds={"wearable_daily"})
            assert len(wear) == 14
            assert wear[0].day == end_date - timedelta(days=13)
            assert wear[-1].day == end_date
            assert seeded.load_baseline(pid).entries[0].valid_from == end_date - timedelta(days=15)
        assert source.read_bytes() == original
    finally:
        get_settings.cache_clear()
        get_store.cache_clear()


def test_twin_does_not_return_expired_wearable_as_current(records_root, monkeypatch):
    import main
    from record.store import get_store

    latest = get_store().load_timeline("P002", kinds={"wearable_daily"})[-1].ts
    future = latest + timedelta(days=40)

    class FutureDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return future.astimezone(tz) if tz else future.replace(tzinfo=None)

    monkeypatch.setattr(main, "datetime", FutureDateTime)
    result = main.twin("P002", x_who="P002")
    assert result["wearable"] == []
    assert result["avatar"]["sleep_hours"] is None
