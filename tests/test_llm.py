from __future__ import annotations

import pytest
from research_agent.llm import (
    FakeLLM,
    LLMClient,
    LLMError,
    LLMResponse,
    StructuredOutputError,
    extract_json,
    schema_hint,
)
from pydantic import BaseModel


class SampleModel(BaseModel):
    name: str
    count: int


def test_extract_json_from_fenced_reply() -> None:
    reply = (
        "Here you go:\n"
        "```json\n"
        '{\n  "name": "alpha",\n  "count": 42\n}\n'
        "```\n"
        "Hope this helps!"
    )
    extracted = extract_json(reply)
    assert extracted == '{\n  "name": "alpha",\n  "count": 42\n}'


def test_schema_hint_contains_json_schema() -> None:
    hint = schema_hint(SampleModel)
    assert "JSON Schema:" in hint
    assert '"name"' in hint
    assert '"count"' in hint


def test_repair_after_one_bad_reply() -> None:
    from research_agent.llm import structured

    fake = FakeLLM(
        script={
            "item_gen": [
                "This is definitely not valid json!",
                '{"name": "beta", "count": 10}',
            ]
        }
    )

    result = structured(
        fake,
        [{"role": "user", "content": "give me a sample"}],
        SampleModel,
        purpose="item_gen",
    )
    assert isinstance(result, SampleModel)
    assert result.name == "beta"
    assert result.count == 10
    # Exactly 2 calls were made
    assert len(fake.calls) == 2
    # Second call contains the error text or feedback
    second_call_msgs = fake.calls[1][1]
    assert any("invalid" in m["content"].lower() or "schema" in m["content"].lower() for m in second_call_msgs)


def test_gives_up_after_repair_fails() -> None:
    from research_agent.llm import structured

    fake = FakeLLM(
        script={
            "item_gen": [
                "bad response 1",
                "still bad response 2",
            ]
        }
    )

    with pytest.raises(StructuredOutputError):
        structured(
            fake,
            [{"role": "user", "content": "give me a sample"}],
            SampleModel,
            purpose="item_gen",
        )

    # Exactly 2 calls were made before giving up
    assert len(fake.calls) == 2


def test_openai_compat_empty_model_raises_llmerror() -> None:
    from research_agent.llm import OpenAICompatLLM

    with pytest.raises(LLMError, match="LLM_MODEL"):
        OpenAICompatLLM(model="")


def test_openai_compat_throttle() -> None:
    import time
    from unittest.mock import MagicMock, patch
    from research_agent.llm import OpenAICompatLLM

    llm = OpenAICompatLLM(model="dummy-model", min_interval_s=0.2)
    with patch.object(llm._client.chat.completions, "create") as mock_create:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
        mock_response.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
        mock_create.return_value = mock_response

        t0 = time.monotonic()
        llm.complete([{"role": "user", "content": "1"}])
        llm.complete([{"role": "user", "content": "2"}])
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.18


def test_openai_compat_provider_down_raises_llmerror() -> None:
    from unittest.mock import MagicMock, patch
    import openai
    from research_agent.llm import OpenAICompatLLM

    llm = OpenAICompatLLM(model="dummy-model")
    with patch.object(
        llm._client.chat.completions,
        "create",
        side_effect=openai.APIConnectionError(request=MagicMock()),
    ):
        with pytest.raises(LLMError):
            llm.complete([{"role": "user", "content": "hello"}])


def test_openai_compat_rate_limit_retry() -> None:
    from unittest.mock import MagicMock, patch
    import openai
    from research_agent.llm import OpenAICompatLLM

    llm = OpenAICompatLLM(model="dummy-model", min_interval_s=0)
    mock_success = MagicMock()
    mock_success.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
    mock_success.usage = MagicMock(prompt_tokens=5, completion_tokens=2)

    with patch("time.sleep") as mock_sleep:
        with patch.object(
            llm._client.chat.completions,
            "create",
            side_effect=[
                openai.RateLimitError(
                    message="Free limit reached: retry after 7s",
                    response=MagicMock(status_code=429),
                    body=None,
                ),
                mock_success,
            ],
        ):
            resp = llm.complete([{"role": "user", "content": "hello"}])
            assert resp.text == '{"ok": true}'
            mock_sleep.assert_called_once()
            assert 6.0 <= mock_sleep.call_args[0][0] <= 8.0


@pytest.mark.live
def test_openai_compat_live_smoke() -> None:
    import json
    from research_agent.config import Settings
    from research_agent.llm import OpenAICompatLLM, extract_json

    settings = Settings.from_env()
    if not settings.llm_api_key or settings.llm_api_key == "your-key-here":
        pytest.skip("LLM_API_KEY not configured for live test")

    client = OpenAICompatLLM(
        base_url=settings.llm_base_url or None,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_s=settings.request_timeout_s,
    )
    resp = client.complete(
        [{"role": "user", "content": 'Respond with JSON: {"ok": true}'}],
        json_mode=True,
    )
    data = json.loads(extract_json(resp.text))
    assert data.get("ok") is True


def test_injected_malformed_fault_is_recovered() -> None:
    from research_agent.llm import FaultyLLM, structured

    inner = FakeLLM(script={"item_gen": ['{"name": "recovered", "count": 100}']})
    faulty = FaultyLLM(inner, faults={"llm:malformed"})

    res = structured(
        faulty,
        [{"role": "user", "content": "give item"}],
        SampleModel,
        purpose="item_gen",
    )
    assert res.name == "recovered"
    assert res.count == 100


def test_injected_down_fault_raises_llmerror() -> None:
    from research_agent.llm import FaultyLLM

    inner = FakeLLM()
    faulty = FaultyLLM(inner, faults={"llm:down"})

    with pytest.raises(LLMError, match="llm:down"):
        faulty.complete([{"role": "user", "content": "give item"}])


def test_fake_llm_returns_scripted_replies_in_order_and_records_calls() -> None:
    fake = FakeLLM(
        script={
            "plan": ['{"step": 1}', '{"step": 2}'],
            "synth": lambda msgs: f"summary for {len(msgs)} messages",
        }
    )

    # First call to 'plan'
    resp1 = fake.complete([{"role": "user", "content": "hi"}], purpose="plan")
    assert resp1.text == '{"step": 1}'

    # Second call to 'plan'
    resp2 = fake.complete([{"role": "user", "content": "next"}], purpose="plan")
    assert resp2.text == '{"step": 2}'

    # Call to callable purpose 'synth'
    resp3 = fake.complete([{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}], purpose="synth")
    assert resp3.text == "summary for 2 messages"

    # Verifies calls are recorded
    assert len(fake.calls) == 3
    assert fake.calls[0][0] == "plan"
    assert fake.calls[0][1] == [{"role": "user", "content": "hi"}]
    assert fake.calls[1][0] == "plan"
    assert fake.calls[2][0] == "synth"


def test_fake_llm_raises_scripted_exception() -> None:
    fake = FakeLLM(script={"plan": [LLMError("Simulated LLM network failure")]})
    with pytest.raises(LLMError, match="Simulated LLM network failure"):
        fake.complete([{"role": "user", "content": "test"}], purpose="plan")
