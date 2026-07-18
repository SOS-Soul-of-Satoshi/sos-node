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
| Genesis SHA-256 | `56f3f8e215a221125171641a3272afa7cb3781079121be509f9cc4db6a3a58b1` |
| Node profile | Pure `verify-only`; no embedded prover and no development RPC |
| Linux binary SHA-256 | `0707cc04785050c8714bd8cb03729ef1e9c71c9379c32b6378aa75e1f72625b6` |
| Windows binary SHA-256 | Pending signed `v0.3.0-testnet` publication |
| Consensus | Two-phase BFT PoS; stake-weighted proposer permutation v2 |
| Nominal block time | 5 seconds |
| Active validators | 4 project-operated identities, currently co-hosted |
| Ethereum bridge | Paused pending a proven validator-set transition |

The current validator processes share one Hetzner host. This testnet therefore
does not demonstrate host or organizational decentralization. Independent
operators, additional failure domains and external audits remain mainnet gates.

Bridge mutations are disabled in the node and wallet. The live SOS
validator-set hash does not currently match the Sepolia V2 contract, so users
must not create an SOS lock or burn wSOS until a reconciled transition and a new
operational check are published.

## Join the network

The public network currently runs the fresh `v0.3.0-testnet` genesis above.
Signed `v0.3.0-testnet` release assets are being staged; do not use older
`v0.1.0` or `v0.2.0-testnet` binaries against this genesis.

```bash
# Verify the hosted genesis:
curl -fsSLo genesis.json https://node.soulofsatoshi.com/genesis.json
echo "56f3f8e215a221125171641a3272afa7cb3781079121be509f9cc4db6a3a58b1  genesis.json" \
  | sha256sum -c -
```

Release assets also include an aggregate `SHA256SUMS` and `SHA256SUMS.sig`.
Verify both the archive hashes and the release signature with the public key
committed in this repository:

```bash
sha256sum -c SHA256SUMS
ssh-keygen -Y verify -f RELEASE_SIGNERS -I sos-release -n sos-release \
  -s SHA256SUMS.sig < SHA256SUMS
```

The expected signing-key fingerprint is
`SHA256:5Ax7PUTlVR0ZpgrQYNDSjeOu/bR9zZZX7PrVAngS2WY`.

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
- Feedback and support: [GitHub Discussions](https://github.com/SOS-Soul-of-Satoshi/sos-node/discussions)

The scheduled probe in [`scripts/sos-public-probe.py`](scripts/sos-public-probe.py)
checks public HTTPS, chain progress, supply conservation, privacy state, bridge
caps/accounting, validator-set agreement with Sepolia, and rejection of the
development RPC surface. A validator-set mismatch is critical whenever bridge
operations are enabled. It is reported as degraded, never healthy, only while
both authoritative operation flags are explicitly false.

## Tested feature matrix

Generation 2 completed end-to-end faucet, signed transparent transfer, shield,
private send, unshield, both bridge directions, proven validator-set rotations,
replay negatives, restart recovery, P2P catch-up and public RPC failover. A
six-hour isolated production-profile chaos/load campaign completed on
2026-07-13. Those results are historical evidence; they do not override the
current bridge pause or establish independent-validator resilience.

## Security notice

This is unaudited testnet software. Testnet tokens have no monetary value. The
Sepolia V2 deployment enforces a 10,000 SOS outstanding cap and a 1,000 SOS
per-deposit cap, but the bridge is currently paused. These controls limit
exposure and do not replace consensus, bridge, cryptographic, wallet or
operations audits. Do not use testnet keys for any other network.

## License

The node binary is distributed for operation of the SOS testnet. See
[`LICENSE`](LICENSE). The Ethereum contracts are published under MIT in the
separate contracts repository.
