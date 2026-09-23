# Luma Voice

Voice is an optional interface. Email and the client portal remain the canonical async path.

## Production architecture

```
Phone
  -> Twilio Programmable Voice
  -> HTTPS TwiML ingress
  -> WSS Twilio Media Stream
  -> Luma realtime bridge
  -> realtime speech model
  -> governed Luma context/actions
  -> audio back to Twilio
```

Twilio Media Streams bidirectional calls use `<Connect><Stream>`; the stream must be publicly reachable over `wss://`. Luma validates Twilio webhook signatures.

## Required production settings

Set:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`
- `LUMA_VOICE_PUBLIC_URL=https://api.example.com`
- `LUMA_VOICE_STREAM_URL=wss://api.example.com/voice/stream`
- `LUMA_VOICE_TWIML_URL=https://api.example.com/voice/twilio/incoming`
- `LUMA_REALTIME_API_KEY`
- `LUMA_REALTIME_URL=wss://api.openai.com/v1/realtime`
- `LUMA_REALTIME_MODEL=gpt-realtime-2.1`
- `LUMA_REALTIME_VOICE=marin`

The realtime provider/model values are configurable so the telephony layer is not locked to one model vendor.

## Custom-number test call

Use an E.164 destination:

`+15551234567`

Call:

`POST /voice/test-call`

Example JSON:

```json
{
  "to": "+15551234567",
  "approved": true
}
```

The endpoint is restricted to owner/admin/operator principals and requires explicit approval. It places one outbound call through the configured Twilio number and routes the call into the Luma voice flow.

For local development, Twilio credentials may be supplied through the environment. Production deployments should normally use the configured secret backend.

## Telephony setup

1. Purchase/verify a Twilio voice-capable number.
2. Configure the Luma API with the Twilio credentials.
3. Make the API publicly reachable over HTTPS.
4. Make `/voice/stream` reachable over WSS.
5. Configure the public URLs above.
6. Place a test call using `POST /voice/test-call`.
7. Confirm the AI identifies itself as AI.
8. Test interruption/barge-in, topic changes, uncertainty, escalation, and the request to continue by email.
9. Test an invalid/unreachable destination and verify the failure is surfaced without retrying indefinitely.

## Production voice behavior

The agent must:

- identify itself as AI;
- never claim to be human;
- use business/project context;
- never invent pricing, commitments, credentials, appointments, or outcomes;
- respect communication preferences and do-not-call state;
- ask before consequential actions;
- escalate when outside its authority;
- support switching to email;
- persist the conversation and outcome;
- send a post-call email summary when configured.

A voice connection is not considered production-ready solely because audio flows. The production bar includes low latency, natural turn-taking, interruption handling, reliable escalation, governed actions, provider signature validation, monitoring, and tested failure behavior.


## Production hardening

The voice path now includes operator-approved E.164 test destinations, Twilio call lifecycle/status persistence, maximum-duration metadata, webhook signature validation, communication-policy primitives, and cancellation cleanup for the realtime bridge.

Production rollout still requires real provider-account validation. In particular, validate the configured realtime model/event contract, public HTTPS/WSS routing, interruption behavior, latency, escalation, failure handling, and post-call email delivery with the actual accounts before marking the integration production-ready.

Voice remains optional: clients can complete the entire Luma engagement through email and the portal.
