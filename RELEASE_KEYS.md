# SOS release signing keys

`RELEASE_SIGNING_KEY.pub` is the active trust anchor for public releases.

| Generation | Fingerprint | Status |
| --- | --- | --- |
| v2 | `SHA256:c9hqz7F4dn6rWUF7ABbG8pLxJ9R45vEA95buNaVjuNE` | Active from `v0.3.1-testnet` |
| v1 | `SHA256:5Ax7PUTlVR0ZpgrQYNDSjeOu/bR9zZZX7PrVAngS2WY` | Retired for new releases |

The v1 public key remains available for historical verification. It must not
be accepted as the signer of `v0.3.1-testnet` or any later release.
