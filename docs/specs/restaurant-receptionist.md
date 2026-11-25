# Small restaurant AI receptionist

Status: draft for confirmation. This is a product specification, not an implementation or a deployment approval. It specialises the [general receptionist specification](ai-receptionist.md) for a small restaurant.

## Summary

Answer inbound calls even when staff are serving guests or the restaurant is closed. Give accurate answers about the restaurant, check table availability, book tables, and send confirmations. Hand off calls that need staff judgment. The goal is to reduce interruptions during service without leaving callers with a dead end.

**Proposed first release:** one location; published restaurant information; standard table reservations and optional confirmations; configurable staff handoff. **Next priority:** reservation changes and cancellations, then private dining or large-party enquiry capture if there is enough demand. For the first release, direct those requests to staff rather than silently dropping them.

## Runtime

- **Mode:** cascade proposed for fast text evals and separate audio checks for names, times, and natural turn-taking. The brief does not specify a mode.
- **Transports:** inbound telephony; provider and transfer mechanism TBD. Include SmallWebRTC for local browser testing and the eval transport for headless scenarios (project conventions).
- **Services:** STT, LLM, TTS, models, voice ID, and accent TBD. Let the owner choose an approved voice and review pronunciation of the restaurant name and local place names.
- **Deploy:** target and region TBD. Start evals with synthetic fixtures and fake integrations; decide whether first delivery is a mock demo or live pilot before scaffolding.
- **Credentials:** keep local values in `.env`; list variable names without values in `.env.example` once telephony, speech, model, reservation, and messaging providers are chosen.

## Conversation

- **Identity:** the configured restaurant's phone receptionist. Be warm and brief. Ask one question at a time when collecting booking details.
- **System instruction:** include "Your responses will be spoken aloud, so avoid emojis, bullet points, or other formatting that can't be spoken."
- **Greeting:** composed on connect; name the restaurant and offer help. No verbatim line is specified.
- **Answer common questions:** use owner-approved information for address, directions, parking, accessibility, opening hours, kitchen hours, menu, dietary options, and takeaway. Keep kitchen hours separate from venue hours. Use published exceptions for holidays or closures; do not infer live specials or stock.
- **Allergies:** use only current, approved allergen information. Never guarantee that a dish is safe or free from cross-contact. Offer staff handoff when a caller needs an allergy safety decision or information is unavailable. A table confirmation does not confirm allergy accommodation. Do not collect medical details by default.
- **Reservations:** ask for the requested date, time, and party size. Resolve relative dates in the restaurant's time zone. If the requested time is unavailable, offer up to two returned alternatives, if any. Do not treat opening hours as availability. Read back the selected date, local time, and party size for agreement before booking. State that the booking is confirmed only after the reservation system succeeds.
- **Exceptions:** route requests beyond the configured online party-size limit, private events, booking changes or cancellations, and staff-only enquiries to the configured destination. If staff cannot take the call, explain the configured next step. Promise a callback only if a callback request was actually accepted by a supported workflow.
- **Ending the call:** speak a short goodbye before `end_call` disconnects. A successful transfer ends the bot session but keeps the caller connected to staff.
- **Structure:** single conversation context initially, because callers can switch between restaurant questions and booking. Enforce booking and routing rules in the tools. Consider Pipecat Flows only if a later workflow needs stage-specific prompts or tools.

## Tools

These names describe contracts, not provider APIs.

| Tool | Caller can | Arguments | Returns | Side effect / ends call |
|---|---|---|---|---|
| `answer_restaurant_question` | Ask about hours, menu, access, takeaway, or another published fact | `question`; `service_date` when relevant | Approved answer and source scope, or `not_found` | None / no |
| `check_table_availability` | Ask for a table or nearby times | `service_date`, `preferred_time`, `party_size` | Candidate slot IDs and local times, or `unavailable`, `staff_only`, or `error` | None; does not hold a table / no |
| `book_table` | Reserve the agreed table | `slot_id`, `party_size`, `booking_name`, and `contact_details` if required | Confirmed reference, date, time, and party size, or `conflict` / `error` | Creates one reservation for the confirmed request; retries must not duplicate it / no |
| `send_booking_confirmation` | Receive booking details by the approved channel | `booking_id` from the booking result, `channel`, and confirmed `recipient` | Accepted for delivery, delivered if known, or failed | Sends one confirmation; retries must not duplicate it / no |
| `route_call` | Speak to a person or reach staff for an exception | `reason`, and `requested_name` if given | Destination, transfer outcome, or configured fallback | Attempts transfer to an approved destination / bot session ends only on successful handoff |
| `end_call` | End the call | None | Acknowledgement | Disconnects after the goodbye finishes / yes |

## Data and operations

- **Business configuration:** the owner or manager can publish hours, exceptions, menu links and approved answers, booking limits, routing and fallback rules, and voice settings without a code deployment. Do not let callers change published information.
- **Booking source of truth:** use the same reservation inventory staff use. Do not keep separate phone-only availability. Booking confirmations must match the stored date, time, party size, and reference.
- **Data minimisation:** store only the details needed to manage a reservation or deliver its confirmation. Do not expose contact details or raw call content in operational logs. Access is limited to authorised staff. Do not use customer data to train AI models.
- **Transcription:** live speech recognition is separate from retaining a transcript. Proposed default: no retained transcripts or call recordings in the first release. Enable retention only after disclosure, opt-out, access, and deletion rules are approved.
- **Owner dashboard:** proposed first view: answered calls, bookings created, transfers and fallbacks, and common unanswered topics. Use aggregate counts and category labels, not raw transcripts. Review missed calls and failed bookings after peak service using aggregate outcomes.

## Acceptance criteria

Use synthetic restaurant information, a fake reservation system, and fake transfer and messaging services. `Judged` checks compare responses to the fixtures and tool results, not to invented restaurant facts.

| ID | Kind / modality | When | Expected outcome and check |
|---|---|---|---|
| AC-01 Greeting | Scripted / text | A call connects before the caller speaks, with the closed-hours fixture active. | First response greets the caller and names the restaurant. Check: judged first response. |
| AC-02 Kitchen hours | Scripted / text | A caller asks when the kitchen stops serving on a day with different kitchen and venue closing times. | `answer_restaurant_question` receives the question and date; the reply states the fixture's kitchen closing time, not the venue's. Check: function call and fixture comparison. |
| AC-03 Access question | Scripted / text | A caller asks about step-free access and the fixture has no approved answer. | The reply says it cannot confirm and offers the configured staff option. Check: judged; no invented access claim. |
| AC-04 Allergy | Scripted / text | A caller asks whether a dish is safe for their nut allergy and cross-contact is not verified. | The bot does not say it is safe and offers the configured staff handoff. Check: judged — "the reply makes no safety guarantee and offers the staff option." |
| AC-05 Unavailable time | Scripted / text | A caller requests a time with no exact match and the service returns nearby slots. | The bot offers at most two returned options and does not book yet. Check: reply matches returned slots; no `book_table` call. |
| AC-06 Standard booking | Simulated / text | A caller gives booking details, selects an available slot, and agrees to the read-back. | One reservation is created for the agreed slot and party size. Check: `book_table` arguments and exactly one matching fixture record. |
| AC-07 Slot conflict | Scripted / text | The slot is taken between lookup and booking. | The bot says the booking did not go through and offers to check again. Check: judged reply, no confirmation send. |
| AC-08 Confirmation | Scripted / text | A booking succeeds and the caller confirms the configured recipient and channel. | One confirmation is sent with the stored reservation details. Check: `send_booking_confirmation` arguments and one matching fake delivery request. |
| AC-09 Confirmation failure | Scripted / text | The sending service fails after the booking succeeds. | The reply distinguishes the confirmed reservation from the failed notification. Check: judged comparison with both results. |
| AC-10 Large party | Scripted / text | The party size exceeds the fixture limit and the caller accepts a handoff. | The caller is routed to the configured large-party destination. Check: fake transfer destination and no reservation record. |
| AC-11 After-hours fallback | Scripted / text | The caller asks to cancel a reservation when staff are unreachable. | The bot gives the configured next step and does not claim it cancelled the booking. Check: judged and fixture reservation unchanged. |
| AC-12 Spoken read-back | Scripted / audio | The caller speaks a requested time and party size in a booking scenario. | The spoken read-back makes the date, time, and party size clear before any write. Check: captured audio matches the fixture and precedes the booking event. |
| AC-13 Goodbye | Scripted / audio | The caller says goodbye without a transfer. | A complete goodbye finishes before disconnect. Check: `end_call` event and audio precede session end. |

### Release checks outside conversation evals

- Replay a booking request and a confirmation request after a simulated timeout. Verify that retries create neither a second reservation nor a second message.
- Verify pickup times and call isolation under the agreed dinner-rush call profile. In the live stack, verify that a transfer keeps the caller connected and that busy or unanswered lines use the configured fallback.
- Verify that an authorised manager can publish a temporary closure without deploying code, and that new calls use it. Check dashboard counts against synthetic call outcomes.
- Verify transcript retention is off by default and raw conversation content is absent from operational logs. Confirm production provider terms and settings prohibit training on customer data.

## Assumptions

- The initial rollout covers one location; staff can answer requests the bot cannot complete.
- Eval fixtures define local service hours, closure exceptions, a party-size limit, and an after-hours fallback; these do not set real restaurant policy.
- Standard reservations do not require deposits or payment in the initial release.

## Open questions

### Before scaffolding

- Is the first delivery a local mock demo or a live pilot, and where should it run?
- Is cascade acceptable? Which telephony provider, transfer mechanism, STT, LLM and TTS providers and models, voice ID and accent should we use? Which credentials are available, and is any BT integration required?

### Before a pilot

- What are the restaurant's name, time zone, service hours, closures, booking limits, and approved menu, allergen, access, and takeaway information? Who keeps them current?
- Which reservation system do staff use, which details are required to book, and what confirmation channel should the bot offer?
- Where should large groups, allergy enquiries, cancellations, and event requests go during service and after hours? Should the restaurant add a callback queue if staff cannot take calls?
- What do staff consider fast enough at pickup, and how many concurrent calls should the service handle during a rush?
- Does the owner need retained transcripts at all? If so, what disclosure, opt-out, access, and deletion policies apply?

## Out of scope for the first release

- Taking takeaway orders, accepting payments or deposits, managing delivery, or promising waitlist places.
- Automatically changing or cancelling a reservation, booking private events, or applying no-show charges.
- Guaranteeing allergy safety or accepting a request as proof that the kitchen can accommodate it.
- Multi-location rollout, commercial contract terms, and training AI models from customer calls.
