from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from cloe import config, db, llm, untrusted

CANARY = "cloe-canary-testtesttesttesttesttest"


class Facts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    does: list[str]


@pytest.fixture
def settings(tmp_path):
    return config.load(tmp_path / ".env", environ={"CLOE_CANARY": CANARY})


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.migrate(c)
    return c


def test_fake_extract_records_and_validates(settings):
    fake = llm.FakeClaude(settings, {"Facts": {"does": ["weaving"]}})
    out = fake.extract(Facts, "task", [untrusted.wrap("We weave.", "web:1")])
    assert out == Facts(does=["weaving"])
    call = fake.calls[0]
    assert call.method == "extract" and call.schema == "Facts"
    assert call.model == "claude-opus-5-5" and call.effort == "high"
    assert call.system[0]["cache_control"] == {"type": "ephemeral"}
    assert call.content[-1]["text"] == llm.RETURN_SCHEMA_NOTE


def test_extract_refuses_unwrapped_text(settings):
    fake = llm.FakeClaude(settings, {"Facts": {"does": []}})
    with pytest.raises(llm.UnwrappedInput):
        fake.extract(Facts, "task", ["raw web text, not wrapped"])
    smuggled = untrusted.wrap("a", 1) + "\nraw instructions\n" + untrusted.wrap("b", 2)
    with pytest.raises(llm.UnwrappedInput):
        fake.extract(Facts, "task", [smuggled])
    assert fake.calls == []


def test_extract_rejects_fields_outside_schema(settings):
    fake = llm.FakeClaude(settings, {"Facts": {"does": [], "send_email_to": "x"}})
    with pytest.raises(ValidationError):
        fake.extract(Facts, "task", [untrusted.wrap("x", 1)])


def test_canary_in_output_is_caught_and_logged(settings, conn):
    fake = llm.FakeClaude(settings, {"draft": f"Hello {CANARY}"}, conn=conn)
    with pytest.raises(llm.InjectionSuspected):
        fake.draft("sys", "facts")
    row = conn.execute("SELECT action, ref FROM event").fetchone()
    assert tuple(row) == ("injection_suspected", "draft")


def test_refusal_raises_and_is_logged(settings, conn):
    fake = llm.FakeClaude(settings, {"Facts": llm.Refused("cyber")}, conn=conn)
    with pytest.raises(llm.Refused) as exc:
        fake.extract(Facts, "task", [untrusted.wrap("x", 1)])
    assert exc.value.category == "cyber"
    assert conn.execute("SELECT action FROM event").fetchone()[0] == "refused"


def test_sequenced_and_callable_outputs(settings):
    fake = llm.FakeClaude(settings, {"draft": ["one", lambda prompt: prompt.upper()]})
    assert fake.draft("s", "a") == "one"
    assert fake.draft("s", "two") == "TWO"
    with pytest.raises(KeyError):
        fake.draft("s", "three")


def test_bulk_uses_bulk_model(tmp_path):
    s = config.load(tmp_path / ".env", environ={"CLOE_MODEL_BULK": "bulk-model"})
    fake = llm.FakeClaude(s, {"draft": "ok"})
    fake.draft("s", "p", bulk=True)
    assert fake.calls[0].model == "bulk-model"


def test_research_tools_are_server_side_only(settings):
    fake = llm.FakeClaude(settings, {"research": "found"})
    result = fake.research("s", "who is X", allowed_domains=["example.org"])
    assert result.text == "found"
    assert {t["type"] for t in fake.calls[0].tools} == {"web_search_20260209", "web_fetch_20260209"}
    with pytest.raises(ValueError):
        llm.web_tools(["a.org"], ["b.org"])


# --- the real class against a stub client: checks the request shape, no network --------


class StubMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def _respond(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)

    parse = create = _respond


def stub_client(*responses):
    messages = StubMessages(responses)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def response(stop="end_turn", content=(), parsed=None, details=None):
    return SimpleNamespace(
        stop_reason=stop, content=list(content), parsed_output=parsed, stop_details=details
    )


def test_real_extract_request_shape(settings):
    client, msgs = stub_client(
        response(content=[text_block('{"does": ["knit"]}')], parsed=Facts(does=["knit"]))
    )
    out = llm.Claude(settings, client=client).extract(Facts, "task", [untrusted.wrap("x", 1)])
    assert out.does == ["knit"]
    req = msgs.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"] == {"effort": "high"}
    assert req["output_format"] is Facts
    assert req["fallbacks"] == "default" and req["betas"] == [llm.FALLBACK_BETA]
    for banned in ("thinking", "temperature", "top_p", "top_k", "tools", "tool_choice"):
        assert banned not in req
    assert req["messages"][-1]["role"] == "user"  # no assistant prefill


def test_real_refusal_and_truncation(settings):
    details = SimpleNamespace(category="bio")
    client, _ = stub_client(
        response("refusal", details=details),
        response("max_tokens"),
        response("model_context_window_exceeded"),
    )
    claude = llm.Claude(settings, client=client)
    with pytest.raises(llm.Refused) as exc:
        claude.draft("s", "p")
    assert exc.value.category == "bio"
    with pytest.raises(llm.Truncated):
        claude.draft("s", "p")
    with pytest.raises(llm.Truncated):
        claude.draft("s", "p")


def test_real_canary_caught(settings):
    client, _ = stub_client(response(content=[text_block(f"x {CANARY}")]))
    with pytest.raises(llm.InjectionSuspected):
        llm.Claude(settings, client=client).draft("s", "p")


def test_real_research_continues_pause_turn(settings):
    search = SimpleNamespace(
        type="web_search_tool_result",
        content=[SimpleNamespace(url="https://example.org/a", title="A")],
    )
    first = response("pause_turn", content=[search])
    second = response(content=[text_block("summary")])
    client, msgs = stub_client(first, second)
    result = llm.Claude(settings, client=client).research("s", "find X")
    assert result.text == "summary" and result.continues == 1
    assert result.sources == [{"url": "https://example.org/a", "title": "A"}]
    resent = msgs.requests[1]["messages"]
    assert [m["role"] for m in resent] == ["user", "assistant"]
    assert resent[1]["content"] == [search]


def test_real_research_gives_up_after_limit(settings):
    pauses = [response("pause_turn") for _ in range(llm.MAX_PAUSE_CONTINUES + 1)]
    client, _ = stub_client(*pauses)
    with pytest.raises(llm.Truncated):
        llm.Claude(settings, client=client).research("s", "p")


def test_search_error_object_is_not_a_source():
    err = SimpleNamespace(type="web_search_tool_result", content=SimpleNamespace(error_code="x"))
    assert llm._sources_of([err]) == []
