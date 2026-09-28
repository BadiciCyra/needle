from app.schemas import Brief, Maturity, StartupProfile


def test_missing_fields_are_computed_from_empty_values():
    brief = Brief(title="Bayi şikayeti sınıflandırma", problem="Şikayetler elle ayrılıyor")
    assert brief.computed_missing_fields() == [
        "scope",
        "required_capabilities",
        "success_criteria",
        "timeline",
    ]


def test_complete_brief_has_no_missing_fields():
    brief = Brief(
        title="t",
        problem="p",
        scope="s",
        required_capabilities=["Türkçe metin sınıflandırma"],
        success_criteria="%80 doğruluk",
        timeline="3 ay",
    )
    assert brief.computed_missing_fields() == []


def test_search_texts_include_capabilities():
    startup = StartupProfile(
        id="s1",
        name="Metinci",
        sector="yazılım",
        maturity=Maturity.mvp,
        location="İstanbul",
        capabilities=["Türkçe NLP", "şikayet sınıflandırma"],
        description="Müşteri metinlerini sınıflandırır.",
    )
    assert "şikayet sınıflandırma" in startup.to_search_text()
