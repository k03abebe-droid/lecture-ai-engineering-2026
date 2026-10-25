from types import SimpleNamespace

from app.ask import ask


class FakeUsage:
    prompt_token_count = 123
    candidates_token_count = 45
    total_token_count = 168


class FakeResponse:
    text = "これはテスト回答です。"
    usage_metadata = FakeUsage()


class FakeModels:
    def __init__(self, response):
        self.response = response

    def generate_content(self, model, contents):
        assert model == "gemini-2.5-flash"
        assert contents == "テスト質問"
        return self.response


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


def test_ask_prints_usage_metadata(monkeypatch, capsys):
    response = FakeResponse()
    monkeypatch.setattr("app.ask.get_api_key", lambda: "fake-key")
    monkeypatch.setattr("app.ask.MODEL", "gemini-2.5-flash")
    monkeypatch.setattr("app.ask.genai.Client", lambda api_key: FakeClient(response))

    result = ask("テスト質問")

    captured = capsys.readouterr()
    assert result == "これはテスト回答です。"
    assert "入力トークン数: 123" in captured.out
    assert "出力トークン数: 45" in captured.out
