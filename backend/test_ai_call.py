"""Provider request-budget and visible-text extraction tests."""
import json

import ai_call


class _FakeResponse:
    status_code = 200

    def iter_lines(self):
        events = [
            {"type": "response.output_text.delta", "delta": "MY "},
            {"type": "response.reasoning_summary_text.delta", "delta": "private reasoning"},
            {"type": "response.output_text.delta", "delta": "FIGHTER"},
            {"type": "response.output_text.done", "text": "MY FIGHTER"},
            {"type": "response.completed", "output_text": "MY FIGHTER", "usage": {"input_tokens": 12, "output_tokens": 8}},
        ]
        return [f"data: {json.dumps(event)}".encode() for event in events]

    def close(self):
        pass


class _FakeRequests:
    def __init__(self):
        self.payload = None

    def post(self, url, headers, json, stream, timeout):
        self.payload = json
        assert stream is True
        return _FakeResponse()


def test_meta_request_respects_configured_token_budget_and_only_collects_output(monkeypatch):
    fake = _FakeRequests()
    monkeypatch.setattr(ai_call, "requests", fake)
    preset = {
        "base": "https://api.meta.ai/v1",
        "model": "test-model",
        "role": "system",
        "effort": True,
    }

    result = ai_call.call(
        preset, "system", "user", "low", 640, "test-key", retries=0,
    )

    assert fake.payload["max_output_tokens"] == 640
    assert result["text"] == "MY FIGHTER"
    assert result["error"] is None
