I'm building a phone assistant for my flower shop, Field & Flower, that takes customer orders.

The bot should be able to:
  - list the available bouquets
  - check if a specific flower is in stock
  - add a flower to the order
  - get a summary of the order
  - set the delivery details
  - place the order
  - end the call

When the call starts, the bot greets the caller with exactly:
"This is Field & Flower, your local flower shop. How can I help you today?"

Services:
  - Twilio for phone calls
  - STT: Soniox
  - LLM: OpenAI
  - TTS: Cartesia
  - Deploy to Pipecat Cloud

This is a demo: use a mock backend for the flower data, and "place the order" only needs to log the order.