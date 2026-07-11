# Soul of Satoshi Node

[![Network smoke](https://github.com/SOS-Soul-of-Satoshi/sos-node/actions/workflows/network-smoke.yml/badge.svg)](https://github.com/SOS-Soul-of-Satoshi/sos-node/actions/workflows/network-smoke.yml)

Soul of Satoshi (SOS) is a post-quantum Layer 1 research implementation with
ML-DSA-65 transaction and consensus signatures, opt-in shielded transfers, and
a proof-authorized Ethereum bridge.

This repository distributes the public testnet node, pins the active genesis,
and runs a credential-free network probe. The full protocol source remains in
the private development repository during testnet.

## Current testnet

| Property | Active value |
|---|---|
| Network | Public pre-mainnet testnet |
| Chain ID | `0x534F53` (`5459795`) |
| Genesis SHA-256 | `265a2ef3417c21af1616d222ab8b793a306046070ba4468619c6be9ebb0816ff` |
| Node profile | Pure `verify-only`; no embedded prover and no development RPC |
| Linux binary SHA-256 | `9f58f03891c949181080538ba9d259bba91b58988ad37a632d3f5e3045a8789b` |
| Consensus | Two-phase BFT PoS; stake-weighted proposer permutation v2 |
| Nominal block time | 5 seconds |
| Active validators | 3 processes on one Hetzner host |
| Ethereum bridge | Capped bidirectional Sepolia beta |

The three-validator deployment proves protocol behavior and recovery, but it is
not operational decentralization: all public validators currently share one
host and one operator. Independent operators and external audits remain
mainnet gates.

## Join the network

Download the `v0.2.0-testnet` asset for your platform from
[Releases](https://github.com/SOS-Soul-of-Satoshi/sos-node/releases), then
verify its adjacent `.sha256` file.

```bash
# Linux example
tar -xzf sos-node-v0.2.0-testnet-linux-x64.tar.gz
sha256sum -c sos-node-v0.2.0-testnet-linux-x64.tar.gz.sha256

# The release includes genesis.json. You can also verify the hosted copy:
curl -fsSLo genesis.json https://node.soulofsatoshi.com/genesis.json
echo "265a2ef3417c21af1616d222ab8b793a306046070ba4468619c6be9ebb0816ff  genesis.json" \
  | sha256sum -c -

./sos-node --datadir "$HOME/.sos-node"
```

The node resolves `seed.soulofsatoshi.com`, connects over libp2p, and verifies
the chain from the pinned genesis. Explicit peers can be supplied with
`--boot-nodes`; `--no-dns-seed` disables DNS discovery.

Default local ports:

| Port | Purpose |
|---|---|
| `8545` | JSON-RPC |
| `30303` | libp2p |

The verify-only binary validates privacy, bridge, and validator-transition
STARK receipts against pinned image IDs. It does not generate proofs and does
not need a GPU. Provers and relayers are separately operated services.

## Public services

- Website: [soulofsatoshi.com](https://soulofsatoshi.com)
- Wallet: [app.soulofsatoshi.com](https://app.soulofsatoshi.com)
- Explorer: [explorer.soulofsatoshi.com](https://explorer.soulofsatoshi.com)
- JSON-RPC and genesis: [node.soulofsatoshi.com](https://node.soulofsatoshi.com)
- Ethereum contracts: [sos-contracts](https://github.com/SOS-Soul-of-Satoshi/sos-contracts)

The scheduled probe in [`scripts/sos-public-probe.py`](scripts/sos-public-probe.py)
checks public HTTPS, chain progress, supply conservation, privacy state, bridge
caps/accounting, validator-set agreement with Sepolia, and rejection of the
development RPC surface.

## Tested feature matrix

The fresh testnet has completed end-to-end faucet, signed transparent transfer,
shield, private send, unshield, SOS-to-Ethereum deposit, Ethereum-to-SOS burn,
validator-set V0-to-V1 rotation, replay negatives, restart recovery, P2P
catch-up, and public RPC failover. A six-hour fault/load campaign is being
completed before the release is marked final.

## Security notice

This is unaudited testnet software. Testnet tokens have no monetary value. The
active bridge enforces a 10,000 SOS outstanding cap and a 1,000 SOS per-deposit
cap; these controls limit exposure but do not replace consensus, bridge,
cryptographic, wallet, and operations audits. Do not use testnet keys for any
other network.

## License

The node binary is distributed for operation of the SOS testnet. See
[`LICENSE`](LICENSE). The Ethereum contracts are published under MIT in the
separate contracts repository.
