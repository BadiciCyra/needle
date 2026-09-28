from app.schemas import REQUIRED_BRIEF_FIELDS
from app.seed_data import load_needs, load_startups


def test_forty_valid_startups_with_unique_ids():
    startups = load_startups()
    assert len(startups) == 40
    assert len({s.id for s in startups}) == 40
    assert all(s.capabilities for s in startups)


def test_twenty_needs_with_organization_units():
    needs = load_needs()
    assert len(needs) == 20
    for need in needs:
        assert need["raw_text"].strip()
        org = need["organization"]
        assert org["author_unit"] and org["owner_unit"]


def test_seed_has_near_miss_for_dealer_complaints():
    """Bayi şikayeti ihtiyacı için hem gerçek aday (NLP) hem 'yakın ama değil' aday (bayi yazılımı) olmalı."""
    by_id = {s.id: s for s in load_startups()}
    assert "Türkçe metin sınıflandırma" in by_id["s01"].capabilities
    assert "bayi yönetim yazılımı" in by_id["s21"].capabilities


def test_required_fields_are_brief_attributes():
    assert set(REQUIRED_BRIEF_FIELDS) <= {"problem", "scope", "required_capabilities", "success_criteria", "timeline"}
