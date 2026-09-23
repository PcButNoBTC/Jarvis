from apps.api.voice import (
    disclosure_text,
    new_session,
    record_turn,
    system_policy,
    twilio_gather_twiml,
    twilio_stream_twiml,
    validate_twilio_signature,
)


def test_voice_is_disclosed_and_optional():
    assert "AI assistant" in disclosure_text()
    assert "email" in disclosure_text().lower()


def test_voice_session_context():
    session = new_session(mode="support", caller="+15551234567")
    record_turn(session, "Can you help with our booking flow?")
    assert session.mode == "support"
    assert session.turns[0]["speaker"] == "caller"


def test_policy_has_authority_boundaries():
    policy = system_policy("sales_assistant")
    assert "Never invent" in policy
    assert "human handoff" in policy


def test_twilio_fallback_and_stream_twiML():
    assert "<Gather" in twilio_gather_twiml("https://example.com/gather", "Hello")
    assert "<Connect><Stream" in twilio_stream_twiml("wss://example.com/voice/stream")


def test_unsigned_webhook_is_rejected_by_default(monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("LUMA_VOICE_ALLOW_UNSIGNED_WEBHOOKS", raising=False)
    assert not validate_twilio_signature("https://example.com/voice", {}, None)
