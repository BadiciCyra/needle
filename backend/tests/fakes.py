"""Testlerde gerçek model yerine kullanılan sahte bileşenler."""


class ScriptedBackend:
    """Sırayla önceden yazılmış cevapları döndüren sahte LLM."""

    model_name = "fake-model"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> str:
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("ScriptedBackend: beklenenden fazla çağrı")
        return self.responses.pop(0)
