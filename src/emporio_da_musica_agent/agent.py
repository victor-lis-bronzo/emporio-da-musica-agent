import os

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

from emporio_da_musica_agent.tools import TOOLS, run_tool

load_dotenv()

MODEL = os.getenv("MODEL", "openai/gpt-oss-120b")
MAX_ITERATIONS = 5
FALLBACK_REPLY = (
    "Desculpe, não consegui resolver isso agora. "
    "Fale com a gente pelo WhatsApp (67) 3341-4444 que a equipe te ajuda!"
)

# max_retries: the SDK already retries HTTP 429 (rate limit) with exponential backoff.
client = OpenAI(
    base_url=os.getenv("BASE_URL", "https://api.groq.com/openai/v1"),
    api_key=os.getenv("GROQ_API_KEY"),
    max_retries=5,
)


def _ask_model(messages: list[dict]):
    """Call the model. Groq answers 400 when the model builds a tool call that breaks the
    schema; that is random, so one more try usually fixes it."""
    try:
        return client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
    except BadRequestError:
        return client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)


def reply(messages: list[dict]) -> str:
    """Answer the last user message. `messages` is the whole conversation and is updated in place.

    Loop: ask the model -> if it requests tools, run them and ask again -> stop at a text answer.
    """
    for _ in range(MAX_ITERATIONS):
        response = _ask_model(messages)
        message = response.choices[0].message

        if not message.tool_calls:  # final answer
            messages.append({"role": "assistant", "content": message.content})
            return message.content

        # Rebuilt by hand so only the fields the API expects are sent back.
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in message.tool_calls
            ],
        })
        for call in message.tool_calls:
            print(f"  [consultando {call.function.name} {call.function.arguments}]")
            result = run_tool(call.function.name, call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    messages.append({"role": "assistant", "content": FALLBACK_REPLY})
    return FALLBACK_REPLY
