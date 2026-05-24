# Overlayer Testnet Daily Transactions

Automated daily on-chain transactions for Overlayer testnet (Sepolia) point farming.

## What It Does

Each run (~31 transactions):
- **Mint** 15 C+ (1 USDC each)
- **Stake** all C+ into sC+
- **Mint** 15 T+ (1 USDT each)
- **Check** Overlayer points via API
- **Report** balances and transaction status

## Requirements

- Python 3.11+
- EVM wallet on Sepolia with:
  - ETH (for gas, ~0.003 per run)
  - USDC (need at least 15, faucet from [Aave](https://staging.aave.com/faucet/))
  - USDT (need at least 15, faucet from [Aave](https://staging.aave.com/faucet/))

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/yossweh/overlayer-daily.git
cd overlayer-daily

# 2. Install dependencies
pip install web3 requests

# 3. Set up your wallet
cp .env.example .env
# Edit .env and add your private key (without 0x prefix)
```

## Setup

### 1. Get Sepolia Testnet Tokens

1. Get Sepolia ETH from any faucet (e.g., [Google Cloud Faucet](https://cloud.google.com/application/web3/faucet/ethereum/sepolia))
2. Get USDC + USDT from [Aave Sepolia Faucet](https://staging.aave.com/faucet/)

### 2. Configure Environment

```bash
cp .env.example .env
nano .env
```

Add your wallet private key:
```
WALLET_PRIVATE_KEY=your_private_key_here_without_0x
```

### 3. Run

```bash
python3 overlayer_daily.py
```

## Automation (Cron)

Run daily at 10 AM UTC:

```bash
crontab -e
```

Add:
```
0 10 * * * cd /path/to/overlayer-daily && source .env && export WALLET_PRIVATE_KEY && python3 overlayer_daily.py >> /var/log/overlayer-daily.log 2>&1
```

## Task Requirements (Overlayer Points)

| Task | Requirement | Points | Status |
|------|-------------|--------|--------|
| Mint | 16 C+ | 100 | Done |
| Stake | 395 C+ | 150 | Done |
| Receive | 74 T+ | 200 | Done |
| Transactions | 34 tx | 1000 | Done |
| Send | 381 T+ | 150 | Pending* |
| Bridge | 365 T+ | 150 | Pending* |

*Send and Bridge require LayerZero OFT contracts which are not yet deployed on Sepolia.

## Current Score

**1450 / 1750 points (83%)**

## Notes

- Private keys are never stored in the script or repo
- Each run costs ~15 USDC + 15 USDT + ~0.003 ETH
- At 15 USDC + 15 USDT per day, you have enough for ~600+ days
- Points are tracked automatically by Overlayer's on-chain indexer

## License

MIT
