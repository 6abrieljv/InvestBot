# bot_Investimento 💹

Bot de analise de acoes via terminal, com indicadores tecnicos e simulador de aporte.

## Requisitos ✅

- Python 3.11+

## Instalacao 📦

```bash
python -m pip install -r bot/requirements.txt
```

## Como usar 🚀

Modo terminal interativo:

```bash
python bot/terminal.py
```

Comando unico:

```bash
python bot/terminal.py /analise PETR4
```

## Comandos 🧰

- `🔎 /analise TICKER` - relatorio completo + simulador de aporte
- `💸 /aporte TICKER` - apenas simulador de aporte
- `💵 /preco TICKER` - apenas preco atual
- `🚪 sair` - encerra o modo terminal

## Configuracao ⚙️

Variaveis de ambiente suportadas:

- `VALOR_APORTE` (padrao: `185.00`)

## Cache 🗂️

O `yfinance` usa cache local em `bot/.cache` para reduzir consultas. Esse diretorio esta ignorado no git.

## Observacoes 📌

- A API do Yahoo pode retornar dados parciais. Nesses casos, o relatorio pode mostrar `N/A`.
- Se nao houver dados suficientes, o bot retorna "acao nao encontrada".
