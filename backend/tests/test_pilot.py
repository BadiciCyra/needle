from app.api.pilot_routes import duration_days


def test_duration_from_brief_timeline():
    assert duration_days("3 ay") == 90
    assert duration_days("6 hafta içinde") == 42
    assert duration_days("10 gün") == 10
    assert duration_days("En kısa sürede") == 90
    assert duration_days(None) == 90

