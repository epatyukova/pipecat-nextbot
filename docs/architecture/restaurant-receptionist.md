# Restaurant receptionist: agent architecture

**Status:** proposed; the agent is not scaffolded. The [restaurant receptionist specification](../specs/restaurant-receptionist.md) defines product behaviour and acceptance criteria. This document describes how the first, single-location release could implement it. It does not select providers or approve deployment.

## Call path and boundaries

```text
Caller ── telephony ────────┐
Browser ─ SmallWebRTC ──────┼─> one Pipecat worker and context per connection
Evals ─── eval transport ───┘

transport input → STT → user context → LLM → TTS → transport output → assistant context
                                       │
                                       └─ tools → session state + restaurant rules
                                                        │
                                                        ├─ published restaurant facts
                                                        ├─ reservation system
                                                        ├─ confirmation service
                                                        └─ telephony handoff
```

Use a cascade pipeline: separate speech-to-text (STT), language model (LLM), and text-to-speech (TTS) services. Text evals exercise the decisions without requiring a call; audio evals exercise speech recognition, turn-taking, and playback. Keep the assistant context aggregator after transport output so it records what actually reaches that part of the pipeline rather than all generated text.

After provider selection, generate the runnable application with the Pipecat CLI and eval support. Keep the scaffold's `bot(runner_args)` entry point, `PipelineWorker` wiring, default turn detection, and lifecycle hooks. Use a single conversation context: callers can move between questions, booking, and staff requests without changing the available tools. Keep state and lifecycle decisions out of the prompt where application code can enforce them.

| Boundary | Responsibility |
|---|---|
| Pipecat entry point and conversation tools | Wire the configured transports and services, greet on connect, collect caller intent, and convert tool results into short spoken replies. Keep per-call state and backend handles in worker-scoped resources. |
| Restaurant rules | Resolve service dates in the restaurant time zone, apply published hours and exceptions, enforce party-size and confirmation rules, and select an approved staff destination or fallback. Do not depend on Pipecat or provider SDKs. |
| Integration adapters | Read published facts, query and write reservations, send confirmations, and transfer live calls. Convert provider outcomes to small, explicit results for the tools. Provide fakes at these same boundaries for tests. |
| Owner configuration and reporting | Publish validated restaurant information independently of code deployment. Expose aggregate outcomes to authorised staff. Keep publishing and reporting off the live conversation path. The storage and owner interface are not yet selected. |

## Key call paths

### Restaurant questions

Read from the published business configuration. Resolve date-specific exceptions before answering and distinguish kitchen hours from venue hours. Return `not_found` when the fact is missing; never fill it in with model knowledge. For allergy safety or cross-contact decisions, use the staff handoff rather than presenting menu facts as a guarantee. Do not collect medical details by default.

### Reservations and confirmations

1. Resolve the date, local time, and party size. Apply the configured booking policy and ask the shared reservation system for availability. A slot returned by lookup is not a hold.
2. Track offered slots and the selected slot in call state. The agent reads back the date, local time, and party size and asks for agreement. Before a write, check that the requested slot matches the current agreed selection. A date, time, or party-size change invalidates that agreement. The exact Pipecat turn signal used to record agreement must be verified against the scaffold; the arguments of a model-generated booking call are not evidence of consent on their own.
3. Submit one logical booking request. The reservation system is authoritative for availability and conflicts at write time. Preserve a stable request identity across retries. If a request times out after dispatch, reconcile its outcome before retrying; do not report success or write again when the outcome is unknown. Verify provider idempotency or a safe reconciliation path before enabling live writes.
4. Offer a confirmation only for a verified booking and a confirmed recipient on an approved channel. Build the message from the stored booking. Deduplicate retries separately from booking retries. If sending fails, keep the booking and distinguish the two outcomes when speaking to the caller.

### Staff handoff and call end

Resolve destinations from approved configuration, not caller-provided numbers. Use staff handoff for allergy safety decisions, large groups, private events, and reservation changes or cancellations. Keep the bot session available until the telephony provider reports the handoff outcome. End the bot session on a successful transfer without hanging up the caller. If staff are unavailable or the transfer fails, give the configured fallback; do not promise an unrecorded callback. A browser or eval fake can check routing decisions but cannot establish that real caller audio survives the handoff.

For an ordinary goodbye, let queued audio finish before ending the worker. On disconnect, clean up session resources and stop pending reads. Treat writes already dispatched as potentially committed: a disconnect or interruption is not a rollback.

## Data and operations

- Read a validated configuration version at the start of each call. Publish updates for new calls without redeploying; keep staff reservation inventory as the source of truth for live availability.
- Keep caller and offer state isolated between calls. Retain only the booking and delivery data needed by the approved systems. Keep call recording and transcript retention off by default; live speech and text still pass through the selected providers. Verify their data handling and no-training terms before a pilot.
- Record structured outcomes for pickup latency, booking, transfer, and fallback. Use non-sensitive category labels for unanswered topics. Do not log raw calls, transcripts, contact details, or credentials. Use the provider's inbound offer events for a missed-call count if available; the bot cannot observe calls that never reach it.
- Bound external operations by timeouts. Do not block one call on another or share mutable conversation state. Size capacity and set pickup targets from the restaurant's dinner-rush profile rather than assuming a concurrency limit.

## Implementation and verification order

1. **Confirm scaffold choices.** Select demo versus pilot, telephony and transfer mechanism, STT/LLM/TTS providers and credentials, voice, and hosting. Validate that the selected transfer mechanism can preserve the caller connection. Do not treat an example from another provider as proof of compatibility.
2. **Prove the eval loop.** Scaffold with eval support and run the generated starter scenario. Add fake restaurant facts, reservations, messaging, and handoff before enabling any live side effects.
3. **Build and verify behaviour.** Unit-test restaurant rules and retry handling. Run the spec's text evals for answers, routing, booking, and notifications. Run audio evals for booking read-back and goodbye; verify ordering against side-effect and disconnect events.
4. **Gate a live pilot separately.** Verify calendar conflicts, duplicate prevention, delivery outcomes, failed transfers and caller continuity, privacy controls, and load. Confirm hours, fallback instructions, booking policy, approved content, data retention, and owner access before taking real customer calls.

Pipecat references: [pipeline termination](https://docs.pipecat.ai/pipecat/learn/pipeline-termination), [eval quickstart](https://docs.pipecat.ai/pipecat/evals/quickstart), and [scripted scenarios](https://docs.pipecat.ai/pipecat/evals/scripted-scenarios). The Context Hub index used for this design was Pipecat 1.17.0; verify concrete APIs against the version selected by the scaffold.
