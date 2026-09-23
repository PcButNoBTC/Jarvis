"""Luma Voice: provider-neutral conversational voice control plane.

Calls are optional. Email/portal remain the canonical async path. This module
owns conversation state, disclosure, authority boundaries, escalation, and
provider-neutral turn handling. A real-time speech provider can plug into the
same session without changing client/project logic.
"""
from __future__ import annotations
import os, time, uuid, base64, hashlib, hmac, re
from dataclasses import dataclass, field
from typing import Any

VOICE_MODES = {"receptionist", "qualification", "scheduling", "support", "client_success", "sales_assistant"}
END_REASONS = {"user_requested", "escalated", "completed", "provider_error", "policy_blocked", "timeout"}
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")

def communication_policy(*, do_not_call: bool = False, preferred_channel: str = "email") -> dict[str, Any]:
    return {"do_not_call": bool(do_not_call), "preferred_channel": preferred_channel or "email", "voice_allowed": not bool(do_not_call)}

def validate_destination(number: str) -> str:
    value=(number or "").strip()
    if not E164_RE.fullmatch(value): raise ValueError("Phone numbers must use E.164 format")
    return value

@dataclass
class VoiceSession:
    id: str
    business_id: str | None = None
    project_id: str | None = None
    caller: str | None = None
    mode: str = "receptionist"
    status: str = "active"
    disclosed: bool = False
    turns: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    pending_actions: list[dict[str, Any]] = field(default_factory=list)
    escalation_reason: str | None = None

def new_session(**kwargs) -> VoiceSession:
    mode=kwargs.pop("mode","receptionist")
    if mode not in VOICE_MODES: raise ValueError("Unknown voice mode")
    return VoiceSession(id=str(uuid.uuid4()), mode=mode, **kwargs)

def system_policy(mode: str) -> str:
    if mode not in VOICE_MODES: raise ValueError("Unknown voice mode")
    return (
        "You are Luma, an AI assistant for a business services company. "
        "You are not a human. Be warm, concise, natural, and conversational. "
        "Listen before answering; do not interrupt; acknowledge corrections. "
        "Never invent pricing, capabilities, appointments, credentials, outcomes, "
        "or commitments. If uncertain, say so and offer email follow-up or a human "
        "handoff. Respect do-not-call and communication preferences. Ask before consequential actions. Only perform "
        "actions explicitly authorized by policy. "
        f"Current mode: {mode}."
    )

def disclosure_text() -> str:
    return "Hi, this is Luma, an AI assistant. I can help you here, or we can continue by email if you prefer."

def normalize_turn(transcript: str, speaker: str = "caller") -> dict[str, Any]:
    text=(transcript or "").strip()
    if not text: raise ValueError("Transcript is required")
    return {"id":str(uuid.uuid4()),"speaker":speaker,"text":text,"at":time.time()}

def conversation_context(session: VoiceSession, max_turns: int = 20) -> dict[str, Any]:
    return {
        "session_id":session.id,"mode":session.mode,"business_id":session.business_id,
        "project_id":session.project_id,"caller":session.caller,
        "facts":session.facts,"turns":session.turns[-max_turns:],
        "pending_actions":session.pending_actions,"policy":system_policy(session.mode),
    }

def record_turn(session: VoiceSession, transcript: str, speaker: str = "caller") -> dict[str, Any]:
    turn=normalize_turn(transcript,speaker); session.turns.append(turn); return turn

def request_escalation(session: VoiceSession, reason: str) -> None:
    session.status="escalated"; session.escalation_reason=reason[:500]

def end_session(session: VoiceSession, reason: str = "completed") -> None:
    if reason not in END_REASONS: raise ValueError("Unknown end reason")
    session.status="completed" if reason=="completed" else reason

def twilio_gather_twiml(action_url: str, prompt: str | None = None, voice: str | None = None) -> str:
    selected_voice=voice or os.getenv("LUMA_TWILIO_VOICE","Polly.Joanna-Neural")
    safe_prompt=(prompt or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    safe_action=action_url.replace("&","&amp;").replace('"',"&quot;")
    return (
        '<?xml version="1.0" encoding="UTF-8"?><Response>'
        f'<Gather input="speech" action="{safe_action}" method="POST" speechTimeout="auto" '
        f'language="en-US"><Say voice="{selected_voice}">{safe_prompt}</Say></Gather>'
        f'<Say voice="{selected_voice}">I did not catch that. You can also continue by email.</Say>'
        '<Hangup/></Response>'
    )

def twilio_stream_twiml(stream_url: str) -> str:
    safe=stream_url.replace("&","&amp;").replace('"',"&quot;")
    return '<?xml version="1.0" encoding="UTF-8"?><Response><Connect><Stream url="'+safe+'"/></Connect></Response>'


def validate_twilio_signature(url: str, params: dict[str, str], signature: str | None) -> bool:
    """Validate Twilio's X-Twilio-Signature HMAC-SHA1 webhook signature."""
    token=os.getenv("TWILIO_AUTH_TOKEN")
    if not token:
        return os.getenv("LUMA_VOICE_ALLOW_UNSIGNED_WEBHOOKS","false").lower()=="true"
    if not signature:
        return False
    payload=url + "".join(k + str(params[k]) for k in sorted(params))
    digest=hmac.new(token.encode(),payload.encode(),hashlib.sha1).digest()
    expected=base64.b64encode(digest).decode()
    return hmac.compare_digest(expected,signature)

def voice_capabilities() -> dict[str, Any]:
    return {
        "optional": True,"canonical_async_channel":"email","modes":sorted(VOICE_MODES),
        "requirements":["natural_voice","barge_in","low_latency_streaming","conversation_memory",
                        "business_context","governed_actions","human_escalation","ai_disclosure",
                        "do_not_call_support","post_call_email_summary"],
        "providers":{"telephony":["twilio","telnyx","existing_phone_system"],"speech_bridge":["realtime_provider"]},
        "status":"control_plane_ready; live telephony and realtime speech require provider credentials and bridge validation",
    }


async def realtime_bridge(twilio_ws, public_url: str | None = None):
    """Bridge Twilio bidirectional media to a configurable realtime speech model."""
    import json
    import websockets

    api_key=os.getenv("LUMA_REALTIME_API_KEY") or os.getenv("OPENAI_API_KEY")
    realtime_url=os.getenv("LUMA_REALTIME_URL","wss://api.openai.com/v1/realtime")
    model=os.getenv("LUMA_REALTIME_MODEL","gpt-realtime-2.1")
    if not api_key:
        raise RuntimeError("LUMA_REALTIME_API_KEY or OPENAI_API_KEY is required")
    separator="&" if "?" in realtime_url else "?"
    ws_url=realtime_url + separator + "model=" + model
    headers={"Authorization":f"Bearer {api_key}","OpenAI-Beta":"realtime=v1"}
    async with websockets.connect(ws_url, additional_headers=headers, max_size=None, ping_interval=20, ping_timeout=20) as ai_ws:
        session_update={
            "type":"session.update",
            "session":{
                "instructions":system_policy("receptionist")+" Speak naturally, briefly, and warmly. You are an AI and must disclose that. The caller can switch to email at any time.",
                "modalities":["audio","text"],
                "voice":os.getenv("LUMA_REALTIME_VOICE","marin"),
                "input_audio_format":"g711_ulaw",
                "output_audio_format":"g711_ulaw",
                "turn_detection":{"type":"server_vad","create_response":True,"interrupt_response":True},
            },
        }
        await ai_ws.send(json.dumps(session_update))
        stream_sid=None
        async def from_twilio():
            nonlocal stream_sid
            while True:
                raw=await twilio_ws.receive_text()
                msg=json.loads(raw)
                event=msg.get("event")
                if event=="start":
                    stream_sid=msg.get("start",{}).get("streamSid") or msg.get("streamSid")
                    await ai_ws.send(json.dumps({"type":"response.create"}))
                elif event=="media":
                    payload=msg.get("media",{}).get("payload")
                    if payload:
                        await ai_ws.send(json.dumps({"type":"input_audio_buffer.append","audio":payload}))
                elif event=="stop":
                    break
        async def to_twilio():
            while True:
                raw=await ai_ws.recv()
                event=json.loads(raw)
                kind=event.get("type","")
                if kind=="response.audio.delta" and stream_sid:
                    await twilio_ws.send_text(json.dumps({"event":"media","streamSid":stream_sid,"media":{"payload":event.get("delta","")}}))
                elif kind=="input_audio_buffer.speech_started" and stream_sid:
                    await twilio_ws.send_text(json.dumps({"event":"clear","streamSid":stream_sid}))
                elif kind in {"error","session.created"}:
                    if kind=="error":
                        await twilio_ws.send_text(json.dumps({"event":"clear","streamSid":stream_sid})) if stream_sid else None
        import asyncio
        tasks=[asyncio.create_task(from_twilio()),asyncio.create_task(to_twilio())]
        done,pending=await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending: task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            exc=task.exception()
            if exc and not isinstance(exc, (RuntimeError, asyncio.CancelledError)): raise exc
