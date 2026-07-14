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
| Genesis SHA-256 | `fc0ae56044642f14f5eee71ef165fea5d0868fdc260c9fd15b4acd5f13805e21` |
| Node profile | Pure `verify-only`; no embedded prover and no development RPC |
| Linux binary SHA-256 | `4452b974b4f189f4cf5356cf6e41146affaf49e24a455d867109cc5b0bfc0368` |
| Windows binary SHA-256 | `922113281a5d2f29a04d147160ed2b5a22a76b7b673074980407d8212ea4f8d2` |
| Consensus | Two-phase BFT PoS; stake-weighted proposer permutation v2 |
| Nominal block time | 5 seconds |
| Active validators | 3 project-operated identities, currently co-hosted |
| Ethereum bridge | Paused pending a proven validator-set transition |

The current validator processes share one Hetzner host. This testnet therefore
does not demonstrate host or organizational decentralization. Independent
operators, additional failure domains and external audits remain mainnet gates.

Bridge mutations are disabled in the node and wallet. The live SOS
validator-set hash does not currently match the Sepolia V2 contract, so users
must not create an SOS lock or burn wSOS until a reconciled transition and a new
operational check are published.

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
echo "fc0ae56044642f14f5eee71ef165fea5d0868fdc260c9fd15b4acd5f13805e21  genesis.json" \
  | sha256sum -c -

./sos-node --datadir "$HOME/.sos-node"
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
