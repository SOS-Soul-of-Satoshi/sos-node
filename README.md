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
| Genesis SHA-256 | `e9c96fb551ac5fd1ef8646df08df2c658fe0c624c869fadf53a8b8c4522b78fc` |
| Node profile | Pure `verify-only`; no embedded prover and no development RPC |
| Linux binary SHA-256 | `5171c7443a4ac17dc84190e50f4508c64de693ead50450b08b60250b0a7285ca` |
| Windows binary SHA-256 | `cc234602536c5957d83dd5dd29710f8401e7c12a9e46c704da716e46abe0d7cf` |
| Consensus | Two-phase BFT PoS; stake-weighted proposer permutation v2 |
| Nominal block time | 5 seconds |
| Active validators | 4: three on Hetzner and one off-host |
| Ethereum bridge | Capped bidirectional Sepolia beta |

The fourth validator gives the public testnet a second host failure domain, and
the chain continues finalizing when one of the four validators is unavailable.
This is still not organizational decentralization: all four are operated by the
project. Independent operators and external audits remain mainnet gates.

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
echo "e9c96fb551ac5fd1ef8646df08df2c658fe0c624c869fadf53a8b8c4522b78fc  genesis.json" \
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

Generation 2 has completed end-to-end faucet, signed transparent transfer,
shield, private send, unshield, SOS-to-Ethereum deposit, two proven
validator-set rotations, replay negatives, restart recovery, P2P catch-up, and
public RPC failover. The active Ethereum-to-SOS withdrawal and a six-hour
production-profile fault/load campaign are in progress before the release is
marked final.

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
