# Wallet Balance Checker

A small, local-first desktop utility for organizing wallet inputs, deriving public addresses, and checking selected cryptocurrency balances.

The app is designed for portfolio and educational use. It accepts TXT, CSV, TSV, XLSX, and pasted text, then extracts:

- BIP39 recovery phrases
- EVM addresses
- Bitcoin addresses

It derives common MetaMask EVM accounts and Bitcoin receive/change paths locally. Balance requests use public addresses only.

## What it checks

The current configuration checks:

- ETH
- WETH
- BNB
- POL
- BTC

The EVM scan uses six networks: Ethereum, BNB Smart Chain, Polygon, Arbitrum One, Optimism, and Base. Bitcoin balances use Blockstream's public API. USD estimates use CoinGecko prices when available.

## Run it

1. Install Python 3.11 or newer.
2. Download or clone this repository.
3. On Windows, double-click **Launch Wallet Audit.bat**, or run:

```powershell
python wallet_audit.py
```

4. Add input files or paste text.
5. Click **Extract and derive**.
6. Click **Check balances**.
7. Click **Export results**.

No third-party Python packages are required.

## Output

The export is organized so a recovery phrase is not repeated for every derived address:

- `seed_phrases_PRIVATE.csv` and `seed_phrases_PRIVATE.txt`: phrases, only when private export is enabled
- `address_mapping.csv`: addresses, paths, and seed IDs without phrases
- `address_portfolio.csv`: one summary row per public address
- `seed_portfolio_PRIVATE.csv`: one aggregate row per seed
- `balances_found_PRIVATE.csv`: only records with at least `0.001` ETH, WETH, BNB, POL, or BTC
- `balances.csv`: raw public-address query records
- `public_addresses.txt`: unique public addresses

## Security

Recovery phrases control funds. Never commit them, upload them, paste them into a website, or use a phrase you still need in an online or untrusted environment. Keep private exports offline, delete them when no longer needed, and review `.gitignore` before making a commit.

This project is a balance checker, not a complete wallet accounting system. It does not inspect every chain, token, NFT, DeFi position, exchange account, or pending transaction. RPC endpoints and price APIs can be unavailable or rate-limited.

## License

MIT
