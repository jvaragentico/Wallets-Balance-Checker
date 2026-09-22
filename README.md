# Wallet Balance Checker

A local-first Python desktop utility for organizing wallet inputs, deriving public EVM addresses, and checking selected balances across popular EVM networks.

## What it checks

- ETH
- WETH
- BNB
- POL

The scanner uses Ethereum, BNB Smart Chain, Polygon, Arbitrum One, Optimism, and Base. Bitcoin scanning has been removed so large batches complete much faster. USD estimates use CoinGecko prices when available.

## Features

- Extracts valid BIP39 recovery phrases and EVM public addresses from TXT, CSV, TSV, XLSX, or pasted text
- Derives MetaMask-compatible accounts using `m/44'/60'/0'/0/index`
- Sends only public addresses to RPC and price services
- Groups results by seed without repeating a phrase for every derived address
- Creates a filtered report for balances of at least `0.001`
- Uses only the Python standard library

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
7. Click **Export results** and choose a folder.

## Output files

- `seed_phrases_PRIVATE.csv` and `seed_phrases_PRIVATE.txt`: phrases, only when private export is enabled
- `address_mapping.csv`: EVM addresses, derivation paths, and seed IDs without phrases
- `address_portfolio.csv`: one summary row per public address
- `seed_portfolio_PRIVATE.csv`: one aggregate row per seed
- `balances_found_PRIVATE.csv`: only records with at least `0.001` ETH, WETH, BNB, or POL
- `balances.csv`: raw public-address query records
- `public_addresses.txt`: unique public addresses

## Security

Recovery phrases control funds. Never commit them, upload them, paste them into a website, or use a phrase you still need in an online or untrusted environment. Keep private exports offline and delete them when no longer needed. The included `.gitignore` excludes the app's private export filenames.

This project is a focused balance checker, not a complete wallet accounting system. It does not inspect every chain, token, NFT, DeFi position, exchange account, or pending transaction. Public RPC endpoints and price APIs can be unavailable or rate-limited.

## License

MIT
