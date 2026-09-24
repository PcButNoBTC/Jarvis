from apps.api.voice import (
    disclosure_text,
    new_session,
    record_turn,
    system_policy,
    twilio_gather_twiml,
    twilio_stream_twiml,
    validate_twilio_signature,
    realtime_session_config,
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


from apps.api.voice import communication_policy, validate_destination

def test_voice_communication_policy_respects_dnc():
    policy = communication_policy(do_not_call=True, preferred_channel="email")
    assert policy["voice_allowed"] is False
    assert policy["preferred_channel"] == "email"

def test_voice_destination_requires_e164():
    assert validate_destination("+15551234567") == "+15551234567"
    import pytest
    with pytest.raises(ValueError):
        validate_destination("555-123-4567")


def test_realtime_session_uses_current_ga_contract():
    config = realtime_session_config("gpt-realtime-2.1", "marin")
    session = config["session"]
    assert session["type"] == "realtime"
    assert session["output_modalities"] == ["audio"]
    assert session["audio"]["input"]["format"] == {"type": "audio/pcmu", "rate": 8000}
    assert session["audio"]["output"]["format"] == {"type": "audio/pcmu", "rate": 8000}


def test_voice_destination_policy_is_explicit():
    from apps.api.voice import communication_policy
    assert communication_policy(do_not_call=False, preferred_channel="phone")["voice_allowed"] is True
    assert communication_policy(do_not_call=True, preferred_channel="email")["voice_allowed"] is False


def test_voice_communication_policy_respects_preferred_channel():
    assert communication_policy(preferred_channel="email")["voice_allowed"] is False
    assert communication_policy(preferred_channel="sms")["voice_allowed"] is False
    assert communication_policy(preferred_channel="voice")["voice_allowed"] is True
