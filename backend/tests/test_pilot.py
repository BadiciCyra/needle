from app.api.pilot_routes import _progress, duration_days, metric_from_criteria
from app.db.models import PilotMetric


def test_duration_from_brief_timeline():
    assert duration_days("3 ay") == 90
    assert duration_days("6 hafta içinde") == 42
    assert duration_days("10 gün") == 10
    assert duration_days("En kısa sürede") == 90
    assert duration_days(None) == 90


def test_metric_suggestion_from_success_criteria():
    assert metric_from_criteria("%85 doğruluk") == {"name": "%85 doğruluk", "unit": "%", "target": 85.0, "direction": "artis"}
    reduce = metric_from_criteria("Müşteri iadelerini %30 azaltmak")
    assert reduce["target"] == 30.0 and reduce["direction"] == "azalis"
    assert metric_from_criteria("Kayıp kaçak oranının yarıya indirilmesi")["target"] is None
    assert metric_from_criteria("  ") is None


def test_progress_toward_target():
    up = PilotMetric(name="doğruluk", baseline=60.0, target=85.0, direction="artis")
    assert _progress(up, 72.5) == (0.5, False)
    assert _progress(up, 90.0) == (1.0, True)
    down = PilotMetric(name="iade", baseline=40.0, target=20.0, direction="azalis")
    assert _progress(down, 30.0) == (0.5, False)
    assert _progress(PilotMetric(name="x", target=None, direction="artis"), 5.0) == (None, None)
