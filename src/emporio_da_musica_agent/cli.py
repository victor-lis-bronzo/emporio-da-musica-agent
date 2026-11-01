from datetime import datetime
from pathlib import Path

from emporio_da_musica_agent.agent import reply
from emporio_da_musica_agent.prompts import build_system_prompt, now_in_store_timezone

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
HELP = "Comandos: /nova (nova conversa), /salvar (grava a conversa em examples/), /sair"


def new_conversation() -> list[dict]:
    return [{"role": "system", "content": build_system_prompt(now_in_store_timezone())}]


def save_conversation(messages: list[dict]) -> Path:
    """Write the conversation (including tool consultations) as markdown."""
    lines = ["# Conversa com o agente da Empório da Música", ""]
    for m in messages:
        if m["role"] == "user":
            lines += [f"**Cliente:** {m['content']}", ""]
        elif m["role"] == "assistant" and m.get("tool_calls"):
            for call in m["tool_calls"]:
                f = call["function"]
                lines += [f"> _consulta: `{f['name']}` {f['arguments']}_", ""]
        elif m["role"] == "assistant":
            lines += [f"**Agente:** {m['content']}", ""]
    EXAMPLES_DIR.mkdir(exist_ok=True)
    path = EXAMPLES_DIR / f"conversa-{datetime.now():%Y%m%d-%H%M%S}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    print("Empório da Música - atendimento virtual")
    print(HELP, "\n")
    messages = new_conversation()

    while True:
        try:
            text = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text == "/sair":
            break
        if text == "/nova":
            messages = new_conversation()
            print("(conversa reiniciada)\n")
            continue
        if text == "/salvar":
            print(f"(salva em {save_conversation(messages)})\n")
            continue

        messages.append({"role": "user", "content": text})
        try:
            print(f"\nAgente: {reply(messages)}\n")
        except Exception as error:  # e.g. network down, invalid key
            messages.pop()  # drop the unanswered question so the history stays valid
            print(f"\nAgente: Tive um problema técnico agora. Pode repetir a pergunta? "
                  f"Se continuar, fale com a gente no WhatsApp (67) 3341-4444.\n(detalhe: {error})\n")


if __name__ == "__main__":
    main()
