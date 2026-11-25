---
name: specification
description: >-
  Convert requirements into a Pipecat voice-bot specification and testable
  acceptance criteria. Use when the user asks for a spec, specification,
  acceptance criteria, or to turn a bot brief into something an implementer
  can build and an eval can check.
---

# Specification

Turn a bot brief into a specification an implementer can build, and into acceptance criteria an eval can check. Stop at the spec. Do not scaffold, edit the bot, or invent API keys, model names, or voice IDs.

Read the brief the user points at. A message in the conversation is a brief. For the shape of a brief and of the spec it becomes, read [examples/flower-shop-assistant.md](examples/flower-shop-assistant.md) and [examples/flower-shop-assistant.spec.md](examples/flower-shop-assistant.spec.md).

Write the spec to `docs/specs/<slug>.md` unless the user names a path. Use a short kebab-case slug from the bot's name. Show the spec in the reply, with assumptions and open questions visible, and wait for confirmation before any implementation.

## What the brief already decides

Record only what the brief states:

- Who the bot is, the channel, and the job.
- Each capability, kept as its own tool. Leave the caller's verbs intact.
- Any sentence that must be spoken verbatim, in quotes.
- Named transport, STT, LLM, TTS, and deploy target.
- Mock versus a real backend, and what a write action actually does (log, store, charge).

Cascade mode follows from a brief that names STT and TTS separately. Realtime mode follows from a speech-to-speech brief. Say which one, and why, in the spec.

## Project conventions to apply

State these as conventions, not as discoveries from the brief:

- The system instruction includes: "Your responses will be spoken aloud, so avoid emojis, bullet points, or other formatting that can't be spoken."
- A telephony bot also includes SmallWebRTC so it can be talked to in a browser without a phone.
- The bot is scaffolded with the eval transport. Cascade bots get text scenarios first.
- Credentials stay in `.env`. The spec names the providers that need keys and leaves the values blank.

Recommend a single conversation context when the same tools and rules apply for the whole call. Recommend Pipecat Flows when a stage must replace the prompt or the tool set. Give one sentence for the choice.

## Gaps

A missing product rule stays a gap. Use an **assumption** only when a criterion cannot be written without a stand-in, keep it to one sentence, and label it so it can be rejected. Use an **open question** for anything that must be answered before scaffolding:

- model name, voice ID, and which API keys exist;
- business rules the brief never states (payment, hours, what an order line is, required delivery fields) when you did not assume them.

## Spec shape

```markdown
# <Bot name>

## Summary
<Who it is, the channel, the job, and demo versus production.>

## Runtime
- Mode: cascade | realtime — <why>
- Transports: <production>; SmallWebRTC for local talk, when the production transport is telephony
- STT / LLM / TTS: <providers from the brief; model and voice ID only if named>
- Deploy: <target, or local only>
- Eval: text scenarios; audio only for a behavior that depends on the speech path

## Conversation
- Identity: <one or two sentences>
- System instruction must include the spoken-aloud sentence
- Greeting: "<exact line>" | composed by the model on connect
- Rules: <only rules the brief states>
- Ending the call: <which capability ends it, and that the goodbye is spoken before the call ends>
- Structure: single context | Flows — <why>

## Tools
### <snake_case_name>
- Caller can: <capability, in the brief's words>
- Arguments: <names and meanings; "none" when the capability takes no input>
- Returns: <what the model needs in order to speak the next line>
- Side effect: <log, store, none>
- Ends the call: yes | no

## Data
- Source: mock | real
- Persists: <what is logged or stored>
- Does not: <payments, live inventory, or anything the brief excludes>

## Acceptance criteria
### AC-1 <short name>
- Kind: scripted | simulated
- Modality: text | audio
- When: <the caller event>
- Expect: <one observable outcome>
- Check: exact text | function_call <name> with <args> | side effect | judged — "<criterion>"

## Assumptions
- <one sentence each>

## Open questions
- <one question each>

## Out of scope
- <non-goals taken from the brief>
```

One tool per capability. Tool names are `snake_case`. Arguments are the inputs the caller supplies. The return value is what the spoken reply must agree with.

## Acceptance criteria

Write criteria a headless eval can run. One behavior each.

- A verbatim line or a named tool call is **scripted**. Quote the line. Name the tool and the arguments that matter.
- A job the caller might phrase in many ways is **simulated**. `Expect` is the bot's side of the goal and may name a tool call.
- Default modality is **text**. Use **audio** only when the behavior depends on transcription, turn-taking, or how the line sounds.
- A spoken reply that lists, confirms, or declines must match the tool result, not a catalog invented in the spec.
- The connect greeting is its own criterion and is checked before the caller speaks.
- Ending the call is its own criterion: the ending tool is called, and a spoken goodbye finishes before the session ends.

## Done

Deliver the spec when all of these are true:

- An implementer who never saw the brief can build the bot from the file.
- Every capability has arguments, a return value, and a side effect.
- Every acceptance criterion names the kind, the modality, and a check.
- Assumptions are labeled, and unanswered provider choices are open questions.
