# v0.3.4 six-hour chaos evidence

This directory contains the retained report for the six-hour SOS testnet chaos
campaign run on 20 July 2026 against source checkpoint
`8e3dc4071a0eb5d97ef476fdb5a91138d128c7ec` (`v0.3.4-testnet`). The campaign
used a fresh four-validator lab cluster and exercised transparent, staking and
proof-dependent privacy traffic while injecting process failures, invalid
traffic, loopback delay and network partitions.

## Result

| Metric | Result |
| --- | ---: |
| Verdict | PASS |
| Duration | 21,682.72 seconds (6 h 1 m 22.72 s) |
| Final height | 5,937 |
| Invariant checks | 21,600 |
| Accepted operations | 4,626 |
| Recorded invariant violations | 0 |
| Fault events | 73 |

The 73 fault events comprise eight validator kills followed by eight restarts,
15 invalid-transaction floods, 15 delay applications/heals and six network
partition/heal cycles. Skipped privacy operations are expected when their
prerequisite notes or prover capacity are unavailable; they are not accepted
state transitions.

| Operation | Submitted | Accepted | Rejected | Skipped |
| --- | ---: | ---: | ---: | ---: |
| Transfer | 1,761 | 1,717 | 44 | 0 |
| Stake | 772 | 754 | 18 | 0 |
| Undelegate | 777 | 735 | 42 | 0 |
| Shield | 738 | 719 | 0 | 19 |
| Private send | 339 | 329 | 0 | 135 |
| Unshield | 378 | 372 | 1 | 166 |

## Files and integrity

- [`chaos-6h-report.json`](chaos-6h-report.json) is the machine-readable test
  report, including every recorded fault and the per-operation totals.
- [`chaos-6h-artifacts.sha256`](chaos-6h-artifacts.sha256) records the exact
  lab binaries and genesis file used by the campaign.

The published files themselves have these SHA-256 digests:

```text
bba81ec9772706a5ee9c7990076b19c64def264714e1d76f4da3875f99b329c6  chaos-6h-report.json
b030aca1886748af52748bd951babde65f245f0a718f719b9323da582210ecad  chaos-6h-artifacts.sha256
```

This is reproducible test evidence, not an independent audit and not a claim
that every adversarial condition or long-term resource limit has been tested.
