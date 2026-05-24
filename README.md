# Overlayer Testnet Daily Transactions

Automated daily on-chain transactions for Overlayer testnet (Sepolia) point farming.

## What it does

- **Mint** 15 C+ (1 USDC each) — 15 tx
- **Stake** all C+ into sC+ — 1 tx
- **Mint** 15 T+ (1 USDT each) — 15 tx
- **Check** Overlayer points via API
- **Report** balances and status

~31 transactions per run.

## Requirements

- Python 3.11+
- `web3` package
- EVM wallet with USDC, USDT, and ETH on Sepolia
- Private key in env: `AGENT_WALLET_PRIVATE_KEY`

## Usage

```bash
python3 overlayer_daily.py
```

## Cron (via Hermes Agent)

Runs daily at 10:00 WIB, delivers report to Telegram.
