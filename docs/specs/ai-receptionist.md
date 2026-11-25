# AI receptionist

Status: draft for confirmation. This document specifies behaviour; it does not authorise implementation or deployment.

## Summary

A telephone receptionist for customers, suppliers, and partners. It answers inbound calls around the clock, uses business-provided information to answer common questions, and routes callers by name, keyword, or conversation context. It can book appointments, send booking confirmations, and transcribe calls under the approved privacy policy. It supports multiple locations and departments. The brief describes a production service; the first delivery's use of mock or live backends is undecided.

## Runtime

- Mode: cascade proposed for the first delivery, because it supports fast text evals and lets us verify transcription and voice quality separately in audio; the brief does not require cascade or realtime.
- Transports: inbound telephony; provider and transfer mechanism are open. SmallWebRTC is for local browser testing (project convention). BT is named in the brief, but this does not establish an integration, hosting commitment, or security certification.
- STT, LLM, and TTS: providers and models are open. The business selects a supported voice and accent; no voice ID or default accent is specified.
- Deploy: target, region, and production service levels are open.
- Eval: scaffold with the eval transport (project convention). Use text scenarios first, with fixture data and fake integrations; use audio for speech-dependent checks. Verify real transfers, delivery, privacy controls, and load separately before launch.
- Credentials: keep local credentials in `.env` and list the names, without values, in `.env.example` once the telephony, AI, and backend providers are selected.

## Conversation

- Identity: the configured business's telephone receptionist. Use its approved tone, wording, and pronunciation guidance.
- System instruction must include: "Your responses will be spoken aloud, so avoid emojis, bullet points, or other formatting that can't be spoken."
- Greeting: composed on connect using the configured business name. The brief does not specify a verbatim greeting. Follow the approved disclosure policy before retaining a transcript.
- Answers: use published information for the relevant location or department. If the scope is ambiguous, clarify it. If no answer is available, say so and offer the configured next step; do not invent business facts.
- Routing: use the requested person, keywords, and relevant call context against the configured directory. Clarify ambiguous matches rather than guessing. If the destination is unavailable or transfer fails, tell the caller and follow the configured fallback. Around-the-clock answering does not imply staff are always available.
- Booking: resolve the location, service, and time before booking. Do not say an appointment is booked until the booking system confirms it; do not say a notification was sent until the sending service reports success.
- Ending the call: for an ordinary goodbye, speak a short goodbye before `end_call` ends the session. A successful transfer is a handoff, not a hang-up or a goodbye.
- Structure: single context initially, because callers can switch between questions, routing, and booking; enforce booking and transfer prerequisites in the tools. Consider Pipecat Flows only if a confirmed intake process requires different prompts or tools per stage.

## Tools

### `answer_business_question`
- Caller can: ask a common business question.
- Arguments: `question`; `location` and `department` when specified or clarified.
- Returns: approved answer and its scope, or `not_found` / `ambiguous`.
- Side effect: none. Ends the call: no.

### `route_call`
- Caller can: ask to speak to a person or department, or explain what they need so the receptionist can route them.
- Arguments: `requested_name`, `location`, and `department` when known; `keywords` and a brief, relevant `reason` from the conversation when needed.
- Returns: destination label and transfer outcome, or clarification choices / configured fallback.
- Side effect: transfers the live caller only when a destination resolves and is available. Ends the call: only the bot session on successful handoff; the caller stays connected.

### `check_appointment_availability`
- Caller can: ask for appointment times.
- Arguments: `service`, `location`, and `preferred_window` (requested date or time range, resolved to the business time zone).
- Returns: available slots with time zones, or no availability / service unavailable.
- Side effect: none; does not reserve a slot. Ends the call: no.

### `book_appointment`
- Caller can: book an appointment.
- Arguments: `slot_id` for the chosen slot and `contact_details` required by the business; exact contact fields are open.
- Returns: confirmed booking reference, time, and location; or conflict / failure status.
- Side effect: creates one appointment for the confirmed request; retries must not create duplicate appointments. Ends the call: no.

### `send_booking_confirmation`
- Caller can: receive a confirmation for a booked appointment.
- Arguments: `booking_id` from the successful booking; `channel` and `recipient` as permitted by business policy and confirmed with the caller.
- Returns: sending status; distinguish accepted for delivery from delivered if both are available.
- Side effect: sends a confirmation through the configured channel; a retry must not send a duplicate. Ends the call: no.

### `end_call`
- Caller can: end the call.
- Arguments: none.
- Returns: acknowledgement that the session is ending.
- Side effect: disconnects after the goodbye finishes. Ends the call: yes.

## Operational capabilities

These are service or dashboard functions, not tools the caller or model can invoke.

| Capability | Inputs | Result and side effect |
|---|---|---|
| Answer inbound calls | Called number, incoming call | Selects the business configuration and connects the caller to the receptionist, including outside staff hours. |
| Publish business configuration | Authorised admin; business facts, locations, directory, hours, routing rules, tone, voice and accent | Validates and publishes settings for subsequent calls without a code change. |
| Transcribe calls | Session audio and applicable transcription permission | Makes the transcript available to authorised staff under the approved policy; does not retain a transcript when retention is not permitted. |
| View dashboard | Authorised admin; date range, location and department filters | Shows call volume, time to answer, and routing and booking outcomes for the selected scope. Metric definitions and trend periods are open. |

## Data and privacy

- Sources: business-controlled information and routing directory, calendar, and confirmation service. Use synthetic fixtures in evals. Production systems and ownership are open.
- Persists: published business configuration, booking records, confirmation status, call metrics, and transcripts only as approved. Retention periods and systems of record are open. Audio recording is not required by the brief.
- Protect tenant and location access boundaries. Limit staff access to caller data according to role and scope. Do not put raw conversations or contact details in operational logs.
- Do not use customer data to train AI models. Before production, verify provider terms and settings, access controls, data handling, and retention. Transcript review is for authorised staff learning and service improvement, not model training.

## Acceptance criteria

Each conversation scenario uses test business data and fake side effects unless noted.

| ID | Kind / modality | When | Expect and check |
|---|---|---|---|
| AC-01 Greeting | Scripted / text | The call connects, before the caller speaks. | First response greets the caller and identifies the configured business. Check: judged — "the first response greets the caller and names the configured business." |
| AC-02 Business answer | Scripted / text | The caller asks for the opening hours of a named location with distinct fixture hours. | `answer_business_question` receives the named location and question; the reply matches that location's fixture without adding unsupported hours. Check: function call arguments and judged comparison with the fixture. |
| AC-03 Missing answer | Scripted / text | The lookup returns `not_found`. | The reply says the answer is unavailable and offers the configured next step. Check: judged — "the reply does not invent an answer and offers the configured next step." |
| AC-04 Route by name | Scripted / text | The caller requests a uniquely named employee. | The caller is handed to the matched destination. Check: `route_call` with `requested_name`; fake transport records the expected destination and successful handoff. |
| AC-05 Route by keyword | Scripted / text | A supplier uses a fixture keyword mapped to a department. | The route matches the configured rule. Check: `route_call` with the relevant keyword; fake transport records the expected department. |
| AC-06 Route by context | Simulated / text | The caller describes a fixture scenario in their own words without naming a destination. | The caller reaches the destination that handles the stated need. Check: expected destination in the fake transport event. |
| AC-07 Ambiguous route | Scripted / text | Two locations have a matching employee name. | No transfer occurs before clarification. Check: no transfer event and judged — "the bot asks a question that distinguishes the two matches." |
| AC-08 Failed transfer | Scripted / text | The transport reports a failed transfer. | The caller hears the configured fallback, not a claim of success. Check: judged comparison with the failed result and fallback fixture. |
| AC-09 Availability | Scripted / text | The caller asks for a specific service, location, and date. | The options offered match available slots. Check: `check_appointment_availability` arguments and judged comparison with fixture slots. |
| AC-10 Booking | Simulated / text | The caller selects an offered slot and provides the required details. | Exactly one appointment is created for the selected slot. Check: `book_appointment` argument `slot_id` and one matching record in the fixture calendar. |
| AC-11 Booking conflict | Scripted / text | The selected slot becomes unavailable before booking. | The receptionist reports that the appointment was not booked. Check: judged reply agrees with the conflict result; no confirmation tool call. |
| AC-12 Confirmation | Scripted / text | A booking succeeds and the caller confirms the permitted recipient and channel. | One confirmation is sent for that booking. Check: `send_booking_confirmation` with matching `booking_id`, `channel`, `recipient`; one fake delivery request. |
| AC-13 Failed confirmation | Scripted / text | The booking succeeds but the sender reports failure. | The reply distinguishes a confirmed booking from a failed notification. Check: judged comparison with both tool results. |
| AC-14 Goodbye | Scripted / audio | The caller says goodbye without requesting a transfer. | The goodbye finishes before disconnect. Check: `end_call` called; audio contains a complete goodbye before the session-end event. |
| AC-15 Voice and pronunciation | Scripted / audio | A configured voice reads a greeting or answer containing a fixture name with an approved pronunciation. | The selected voice is used and the name is understandable as prescribed. Check: runtime voice setting plus human review of captured audio against the approved sample. |
| AC-16 Transcript allowed | Scripted / audio | A caller says a known phrase and the fixture policy allows transcript retention. | One transcript linked to the call contains that phrase. Check: transcript store side effect. |
| AC-17 Transcript prohibited | Scripted / audio | A call takes place under a fixture policy that prohibits transcript retention. | No durable transcript is created. Check: no transcript in test storage, logs, or dashboard results. |

### Service and release checks

These checks complement conversation evals; load, dashboard, and privacy cannot be verified from a spoken reply.

- **After-hours operation:** under a closed-hours fixture, the test call gets a greeting and a routing attempt follows the configured after-hours policy.
- **Fast pickup and peak traffic:** measure inbound offer to first audible greeting, successful answer rate, and session isolation under normal and peak load; release gates require agreed thresholds and a peak call profile. Do not treat “never miss a call” as a literal guarantee.
- **Configuration and dashboard:** an authorised test admin publishes a change without deploying code, the next call uses it, and synthetic call totals and outcomes match the dashboard's filters. An admin cannot read another tenant's records.
- **Production integrations and privacy:** verify caller continuity on live-stack transfers, calendar and confirmation behaviour, access restrictions, and provider no-training settings and terms before launch. Use test accounts and synthetic data.

## Assumptions

- For acceptance fixtures, the business publishes a directory, location hours, and an explicit fallback for each route.
- For acceptance fixtures, the caller chooses a slot before the booking tool writes to the calendar.
- For acceptance fixtures, the transcript policy can be set to allow or prohibit retention independently of the speech recognition needed during the call.

## Open questions

### Before scaffolding

- Which telephony provider and transfer mechanism should we use, and is any BT integration required?
- Is cascade acceptable, and which STT, LLM, and TTS providers, models, voice ID, and accent should we use? Which provider credentials are already available?
- Is the first delivery a local mock demo or a pilot with real backends? Where will it run, and what hosting region is required?

### Before pilot or launch

- What businesses, languages, locations, departments, public information, and directory entries are in the first rollout? Who approves and updates them?
- Which signal takes priority if name, keyword, and context disagree? What are the fallback and escalation rules for ambiguity, closed hours, busy lines, no answer, and platform outages?
- Which appointment system, appointment types, durations, time zones, required contact fields, and confirmation channels are supported? Are rescheduling and cancellation required later?
- Is lead qualification or legal intake required in the first rollout? If so, what may the receptionist collect, and when must it hand off to a human?
- What disclosure and opt-out policy applies to transcription, and what retention, deletion, residency, staff access, and provider controls are required for caller data?
- What pickup, availability, concurrent-call, transfer, and speech-quality targets define release readiness? What peak traffic should the load test use?
- What dashboard metrics and filters are required, and how much onboarding time is acceptable for a nontechnical administrator?

## Out of scope for the initial agent

- Contract duration, seasonal pricing, and billing. The brief's 30-day contracts are a commercial requirement, not caller behaviour.
- Automatic model training from business information or call transcripts. Business customisation uses published configuration and approved content.
- Estate-agent lead qualification and legal-case intake beyond routing until their workflows and data rules are specified.
