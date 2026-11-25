# Field & Flower phone assistant

Worked output for [flower-shop-assistant.md](flower-shop-assistant.md). The catalog, the order-line type, and the delivery fields are not in the brief; they stay assumptions or open questions.

## Summary

Field & Flower is a phone assistant that takes customer orders for a flower shop. This is a demo: flower data comes from a mock backend, and placing an order logs the order.

## Runtime

- Mode: cascade — the brief names STT and TTS as separate services.
- Transports: Twilio for phone calls; SmallWebRTC for local browser talk (project convention for a telephony bot).
- STT: Soniox. LLM: OpenAI. TTS: Cartesia. Model name and voice ID are not in the brief.
- Deploy: Pipecat Cloud.
- Eval: text scenarios. Audio only if a later brief asks to check transcription of names, addresses, or the greeting as spoken.

## Conversation

- Identity: the shop assistant for Field & Flower, a local flower shop. It takes bouquet and flower orders over the phone.
- System instruction must include: "Your responses will be spoken aloud, so avoid emojis, bullet points, or other formatting that can't be spoken."
- Greeting, spoken exactly on connect: "This is Field & Flower, your local flower shop. How can I help you today?"
- Rules: the brief states none beyond the greeting and the capability list.
- Ending the call: `end_call` ends the session after the model has spoken a goodbye.
- Structure: single context — the same tools and rules apply for the whole call.

## Tools

### list_bouquets

- Caller can: list the available bouquets
- Arguments: none
- Returns: the bouquets the mock catalog currently offers
- Side effect: none
- Ends the call: no

### check_stock

- Caller can: check if a specific flower is in stock
- Arguments: `flower` — the flower the caller named
- Returns: whether that flower is in stock
- Side effect: none
- Ends the call: no

### add_to_order

- Caller can: add a flower to the order
- Arguments: `flower` — the flower to add; `quantity` — how many, when the caller gives a number
- Returns: the updated order lines
- Side effect: updates the in-session order
- Ends the call: no

### order_summary

- Caller can: get a summary of the order
- Arguments: none
- Returns: the current order lines
- Side effect: none
- Ends the call: no

### set_delivery

- Caller can: set the delivery details
- Arguments: the fields in the delivery assumption below
- Returns: the delivery details now stored on the order
- Side effect: updates the in-session order
- Ends the call: no

### place_order

- Caller can: place the order
- Arguments: none beyond the order already collected
- Returns: a confirmation that the order was logged
- Side effect: logs the order; does not charge a card or call a real shop system
- Ends the call: no

### end_call

- Caller can: end the call
- Arguments: none
- Returns: acknowledgement that the call is ending
- Side effect: ends the session after the goodbye has been spoken
- Ends the call: yes

## Data

- Source: mock, in-process flower data for the demo.
- Persists: `place_order` writes a log line for the order. The order itself lives for the session.
- Does not: take payment, update a live inventory, or send the order to a real fulfillment system.

## Acceptance criteria

### AC-1 Greeting

- Kind: scripted
- Modality: text
- When: the call connects, before the caller speaks
- Expect: the first spoken line is exactly "This is Field & Flower, your local flower shop. How can I help you today?"
- Check: exact text

### AC-2 List bouquets

- Kind: scripted
- Modality: text
- When: the caller asks which bouquets are available
- Expect: `list_bouquets` is called, and the spoken reply names only bouquets in the tool result
- Check: function_call `list_bouquets`; judged — "the reply lists bouquet names and adds none that the tool result did not return"

### AC-3 Check a flower

- Kind: scripted
- Modality: text
- When: the caller asks whether a named flower is in stock
- Expect: `check_stock` is called with that flower, and the spoken reply agrees with the tool result
- Check: function_call `check_stock` with `flower` equal to the name the caller used

### AC-4 Add to the order

- Kind: scripted
- Modality: text
- When: the caller asks to add a named flower
- Expect: `add_to_order` is called with that flower
- Check: function_call `add_to_order` with `flower` equal to the name the caller used

### AC-5 Summarize the order

- Kind: scripted
- Modality: text
- When: the caller asks for the order so far
- Expect: `order_summary` is called, and the spoken reply matches the returned lines
- Check: function_call `order_summary`

### AC-6 Set delivery

- Kind: scripted
- Modality: text
- When: the caller gives delivery details
- Expect: `set_delivery` is called with those details
- Check: function_call `set_delivery` with the fields the caller stated

### AC-7 Place an order

- Kind: simulated
- Modality: text
- When: a caller wants a flower order delivered and supplies a flower, a quantity, and delivery details
- Expect: the bot reads the order back, calls `place_order`, and the order is logged
- Check: judged — "the bot confirmed the order and a place_order tool was called"; side effect — the order was logged

### AC-8 End the call

- Kind: scripted
- Modality: text
- When: the caller says goodbye
- Expect: the bot speaks a short goodbye and `end_call` is called
- Check: function_call `end_call`; judged — "the reply is a spoken goodbye with no formatting that cannot be spoken"

## Assumptions

- An order line is a flower with a quantity. "List the available bouquets" stays a separate capability and does not by itself add a bouquet to the order.
- Delivery details are the recipient name, the address, and the delivery day. `set_delivery` stores those three fields.
- The mock catalog is a fixed in-code list. Acceptance checks compare speech with the tool result, so the spec does not freeze the item names.
- Quantity defaults to 1 when the caller names a flower and no number.

## Open questions

- Which OpenAI model, which Cartesia voice ID, and which Soniox model should the scaffold use?
- Are the OpenAI, Cartesia, Soniox, Twilio, and Pipecat Cloud credentials available?
- Can the caller add a bouquet by name, or only a flower?
- Should a flower that `check_stock` reports as unavailable be refused by `add_to_order`?

## Out of scope

- A real inventory or shop backend.
- Payment.
- Sending the placed order anywhere other than the demo log.
