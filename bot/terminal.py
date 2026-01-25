import sys
from commands import build_response


def _print_help():
    print("✨ Comandos disponíveis:")
    print("  🔎 /analise TICKER  - relatório completo + aporte")
    print("  💸 /aporte TICKER   - simulação de aporte mensal")
    print("  💵 /preco TICKER    - preço atual do ativo")
    print("  🚪 sair             - encerra o modo terminal")


def _run_command(command):
    response = build_response(command)
    if response:
        print(response)
        return
    print("⚠️ Comando inválido. Use /analise, /aporte ou /preco.")


def main():
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        _run_command(command)
        return

    print("💻 Modo terminal ativo.")
    _print_help()
    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaindo.")
            break

        if not line:
            continue
        lowered = line.lower()
        if lowered in {"sair", "/sair", "exit", "quit"}:
            print("Saindo.")
            break

        _run_command(line)


if __name__ == "__main__":
    main()
