# Soul of Satoshi Node

[![Network smoke](https://github.com/SOS-Soul-of-Satoshi/sos-node/actions/workflows/network-smoke.yml/badge.svg)](https://github.com/SOS-Soul-of-Satoshi/sos-node/actions/workflows/network-smoke.yml)

Soul of Satoshi (SOS) is a post-quantum Layer 1 research implementation with
ML-DSA-65 transaction and consensus signatures, opt-in shielded transfers, and
a proof-authorized Ethereum bridge.

This repository distributes the public testnet node, pins the active genesis,
and runs a credential-free network probe. The full protocol source remains in
the private development repository during testnet.

## Download the current testnet node

**Current release: [`v0.3.4-testnet`](https://github.com/SOS-Soul-of-Satoshi/sos-node/releases/tag/v0.3.4-testnet)**

| Platform | Download | Archive SHA-256 |
|---|---|---|
| Linux x86_64 | [`sos-node-v0.3.4-testnet-linux-x86_64.tar.gz`](https://github.com/SOS-Soul-of-Satoshi/sos-node/releases/download/v0.3.4-testnet/sos-node-v0.3.4-testnet-linux-x86_64.tar.gz) | `0c336c152260303cf3c644c2a07d3d930f6505a217d400fa0e4810f0d666d2e0` |
| Windows x86_64 | [`sos-node-v0.3.4-testnet-windows-x86_64.zip`](https://github.com/SOS-Soul-of-Satoshi/sos-node/releases/download/v0.3.4-testnet/sos-node-v0.3.4-testnet-windows-x86_64.zip) | `d34f4a6ed1ea9f1558ff1ca4d61a9e3880a0b0b6eed6a34a4400810db40287d5` |

Download the matching checksum sidecar from the
[`v0.3.4-testnet` assets](https://github.com/SOS-Soul-of-Satoshi/sos-node/releases/tag/v0.3.4-testnet#assets)
and verify the signed
[`RELEASE-MANIFEST.json`](https://github.com/SOS-Soul-of-Satoshi/sos-node/releases/download/v0.3.4-testnet/RELEASE-MANIFEST.json)
before running either package. This is unaudited public testnet software, not a
mainnet release.

## Current testnet

| Property | Active value |
|---|---|
| Network | Public pre-mainnet testnet |
| Chain ID | `0x534F53` (`5459795`) |
| Genesis SHA-256 | `6d20c7a7e6fa4706d4f9e2bcc0ad23c8a144601aee391301ef0912e3c809e524` |
| Node profile | Pure `verify-only`; no embedded prover and no development RPC |
| Linux binary SHA-256 | `9061078b9fed01e2140731feaf07d8e4b9247c286e56e5884e861d618c6cc94a` |
| Windows binary SHA-256 | `387fe4f37807562bebbeac69a723583cd884bd2a504dafe994dc837345b3ace2` |
| Consensus | Two-phase BFT PoS; stake-weighted proposer permutation v2 |
| Nominal block time | 1 second |
| Active validators | 4 project-operated identities across Hetzner and a separate lab host |
| Ethereum bridge | Sepolia Route2 live; capped intake enabled and fail-closed monitored |

Three validator processes share one Hetzner host and the fourth runs on a
separate lab host and network. This gives the testnet two physical failure
domains, but it does not demonstrate organizational decentralization.
Independent operators and external audits remain mainnet gates.

Both SOS-to-Sepolia and Sepolia-to-SOS capped canaries completed, including
replay rejection. Bridge intake is enabled for the capped public testnet and is
guarded by fail-closed checks for contract identity, TVL accounting,
validator-set parity, relayer health and monitoring. The pinned Route2 contract is
`0xB8863C0c094DE2f3f0C50EF96101b53B7374F0C9`, with bridge domain
`0xb706d5afab98a2371bc5593e86be8ee1262f94dff4c1577741e1f506dd1a27ea`.

## Join the network

The public network uses the `v0.3.4-testnet` Route2 release and genesis above.
Do not use `v0.3.3-testnet` or older binaries against this genesis.

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
sha256sum -c sos-node-v0.3.4-testnet-linux-x86_64.tar.gz.sha256
tr -d '\r' < sos-node-v0.3.4-testnet-windows-x86_64.zip.sha256 | sha256sum -c -
cosign verify-blob \
  --bundle RELEASE-MANIFEST.sigstore.json \
  --certificate-identity \
    "https://github.com/SOS-Soul-of-Satoshi/sos-core/.github/workflows/publish-testnet-release.yml@refs/tags/v0.3.4-testnet" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  RELEASE-MANIFEST.json
```

The `tr` normalization makes the current Windows-generated sidecar portable to
POSIX `sha256sum`; it does not alter the downloaded ZIP or its signed digest.

The release manifest is signed keylessly by the protected GitHub Actions tag
workflow. The Windows ZIP is bound by that Sigstore manifest; the executable
does not currently carry an Authenticode signature. The committed SSH keys are
retained only to verify historical releases.

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
- Community and live network status: [SOS Discord](https://discord.gg/dbbjsFBchP)
- Feedback and support: [GitHub Discussions](https://github.com/SOS-Soul-of-Satoshi/sos-node/discussions)
- Support policy and report forms: [SUPPORT.md](SUPPORT.md)

The scheduled probe in [`scripts/sos-public-probe.py`](scripts/sos-public-probe.py)
checks public HTTPS, chain progress, supply conservation, privacy state, bridge
caps/accounting, validator-set agreement with Sepolia, and rejection of the
development RPC surface. A validator-set mismatch is critical whenever bridge
operations are enabled. It is reported as degraded, never healthy, only while
both authoritative operation flags are explicitly false.

## Tested feature matrix

Generation 3 completed end-to-end faucet, signed transparent transfer, shield,
private send, unshield, both bridge directions, proven validator-set rotations,
replay negatives, restart recovery, P2P catch-up and public RPC failover. An
isolated four-validator production-profile chaos/load campaign built from the
exact `v0.3.4-testnet` tagged source ran for six hours on 2026-07-20 with zero
reported invariant violations. Its machine-readable report and artifact hashes
are retained in
[`evidence/v0.3.4-testnet/`](evidence/v0.3.4-testnet/). The Route2 deployment
passed capped canaries in both directions and remains enabled behind the
operational guard. Those results are testnet evidence and do not establish
independent-operator resilience.

## Security notice

This is unaudited testnet software. Testnet tokens have no monetary value. The
Sepolia V2 deployment enforces a 10,000 SOS outstanding cap and a 1,000 SOS
per-deposit cap. The enabled bridge is capped, unaudited testnet infrastructure,
not a production asset bridge. These controls limit exposure and do not replace consensus,
bridge, cryptographic, wallet or operations audits. Do not use testnet keys for
any other network.

## License

The node binary is distributed for operation of the SOS testnet. See
[`LICENSE`](LICENSE). The Ethereum contracts are published under MIT in the
separate contracts repository.
