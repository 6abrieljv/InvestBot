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
- `BRAPI_TOKEN` (ou `BRAPI_API_KEY`) para liberar dados da brapi.dev em qualquer ticker
- `PRICE_MATCH_TOLERANCE` tolerancia de divergencia de preco (padrao: `0.02` = 2%)
- `USE_INVESTIDOR10` habilita a fonte extra de FIIs (padrao: `1`)

Exemplo com `.env`:

```
BRAPI_TOKEN=seu_token_aqui
PRICE_MATCH_TOLERANCE=0.02
```

## Fontes de dados 🧩

O bot usa duas fontes e faz fallback automatico quando uma falha:

- **Yahoo Finance (via `yfinance`)**: precos e historico (OHLC/volume)
- **brapi.dev (SDK oficial)**: cotacoes, historico e dados fundamentalistas (P/VP, DY, etc)
- **Investidor10 (FIIs)**: P/VP, DY e dados patrimoniais quando outras fontes falham

Para tickers fora das 4 acoes gratuitas da brapi (PETR4, MGLU3, VALE3, ITUB4),
e necessario configurar `BRAPI_TOKEN` para liberar P/VP, dividend yield,
liquidez e outros dados.

## Cache 🗂️

O `yfinance` usa cache local em `bot/.cache` para reduzir consultas. Esse diretorio esta ignorado no git.

## Observacoes 📌

- A API do Yahoo pode retornar dados parciais. Nesses casos, o relatorio pode mostrar `N/A`.
- Se nao houver dados suficientes, o bot retorna "acao nao encontrada".
