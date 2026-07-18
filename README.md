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
| Genesis SHA-256 | `6d20c7a7e6fa4706d4f9e2bcc0ad23c8a144601aee391301ef0912e3c809e524` |
| Node profile | Pure `verify-only`; no embedded prover and no development RPC |
| Linux binary SHA-256 | `683b60a7992ed56378916714dc34ebdeb45dadab8e291eeeb4c5b0c490583113` |
| Windows binary SHA-256 | `3c6e5212fb67106447163b8fc20758927c0555a69136eaa1aeaaa614ff9d884f` |
| Consensus | Two-phase BFT PoS; stake-weighted proposer permutation v2 |
| Nominal block time | 5 seconds |
| Active validators | 4 project-operated identities, currently co-hosted |
| Ethereum bridge | Sepolia Route2 pinned; paused until the `v0.3.1-testnet` deployment canary completes |

The current validator processes share one Hetzner host. This testnet therefore
does not demonstrate host or organizational decentralization. Independent
operators, additional failure domains and external audits remain mainnet gates.

Bridge mutations remain disabled until the final release deployment and public
two-way canary complete. The pinned Route2 contract is
`0xB8863C0c094DE2f3f0C50EF96101b53B7374F0C9`, with bridge domain
`0xb706d5afab98a2371bc5593e86be8ee1262f94dff4c1577741e1f506dd1a27ea`.

## Join the network

The public network uses the fresh `v0.3.1-testnet` Route2 genesis above. Do not
use `v0.3.0-testnet` or older binaries against this genesis.

```bash
# Verify the hosted genesis:
curl -fsSLo genesis.json https://node.soulofsatoshi.com/genesis.json
echo "6d20c7a7e6fa4706d4f9e2bcc0ad23c8a144601aee391301ef0912e3c809e524  genesis.json" \
  | sha256sum -c -
```

Release assets include checksum sidecars and a signed
`RELEASE-MANIFEST.json`. Verify the archive hashes and then the manifest with
the allowed signers committed in this repository:

```bash
sha256sum -c sos-node-v0.3.1-testnet-linux-x86_64.tar.gz.sha256
sha256sum -c sos-node-v0.3.1-testnet-windows-x86_64.zip.sha256
ssh-keygen -Y verify -f RELEASE_SIGNERS -I sos-release -n sos-release \
  -s RELEASE-MANIFEST.sshsig < RELEASE-MANIFEST.json
```

The active signing-key fingerprint for `v0.3.1-testnet` and later is
`SHA256:c9hqz7F4dn6rWUF7ABbG8pLxJ9R45vEA95buNaVjuNE`. The retired v1 public key
is retained only to verify historical releases.

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
