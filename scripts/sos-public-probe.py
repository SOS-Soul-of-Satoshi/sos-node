#!/usr/bin/env python3
"""Off-host, secret-free probe for the SOS public testnet."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


USER_AGENT = "sos-public-testnet-probe/1"
HEX32 = re.compile(r"^0x[0-9a-f]{64}$")


class ProbeError(RuntimeError):
    pass


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None else int(value)


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ProbeError("boolean is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 16 if value.startswith("0x") else 10)
    raise ProbeError(f"unsupported integer value: {value!r}")


def hex32(value: Any) -> str:
    if not isinstance(value, str):
        raise ProbeError("expected a 32-byte hex string")
    normalized = value.lower()
    if not normalized.startswith("0x"):
        normalized = "0x" + normalized
    if not HEX32.fullmatch(normalized):
        raise ProbeError(f"invalid bytes32 value: {value!r}")
    return normalized


def request_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise ProbeError(f"{url} returned HTTP {response.status}")
            decoded = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, json.JSONDecodeError) as exc:
        raise ProbeError(f"request to {url} failed: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ProbeError(f"{url} returned a non-object JSON response")
    return decoded


def rpc_raw(url: str, method: str, params: list[Any], timeout: float) -> dict[str, Any]:
    return request_json(
        url,
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout,
    )


def rpc(url: str, method: str, params: list[Any], timeout: float) -> Any:
    response = rpc_raw(url, method, params, timeout)
    if response.get("error") is not None:
        raise ProbeError(f"{method} returned {response['error']!r}")
    if "result" not in response:
        raise ProbeError(f"{method} returned no result")
    return response["result"]


def check_https(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Range": "bytes=0-511"},
        method="GET",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            sample = response.read(512)
            status = response.status
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise ProbeError(f"GET {url} failed: {exc}") from exc
    if status not in (200, 206):
        raise ProbeError(f"GET {url} returned HTTP {status}")
    if not sample:
        raise ProbeError(f"GET {url} returned an empty body")
    return {
        "status": "ok",
        "statusCode": status,
        "latencyMs": round((time.monotonic() - started) * 1000),
        "bytesSampled": len(sample),
    }


def request_bytes(url: str, timeout: float, limit: int = 1_048_576) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise ProbeError(f"GET {url} returned HTTP {response.status}")
            body = response.read(limit + 1)
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise ProbeError(f"GET {url} failed: {exc}") from exc
    if len(body) > limit:
        raise ProbeError(f"GET {url} exceeded the {limit}-byte limit")
    if not body:
        raise ProbeError(f"GET {url} returned an empty body")
    return body


def run_probe() -> dict[str, Any]:
    timeout = float(os.environ.get("SOS_PROBE_TIMEOUT_SECONDS", "15"))
    sos_rpc = os.environ.get("SOS_PUBLIC_RPC", "https://node.soulofsatoshi.com")
    genesis_url = os.environ.get(
        "SOS_PUBLIC_GENESIS_URL", "https://node.soulofsatoshi.com/genesis.json"
    )
    expected_genesis_sha256 = os.environ.get(
        "SOS_EXPECTED_GENESIS_SHA256",
        "265a2ef3417c21af1616d222ab8b793a306046070ba4468619c6be9ebb0816ff",
    ).lower()
    expected_genesis_validators = env_int("SOS_EXPECTED_GENESIS_VALIDATORS", 3)
    eth_rpc = os.environ.get(
        "SOS_ETH_RPC", "https://ethereum-sepolia-rpc.publicnode.com"
    )
    bridge_contract = os.environ.get(
        "SOS_BRIDGE_CONTRACT", "0x862Bc5c5BEa4a32020dc450390Fc25d75BE79e93"
    ).lower()
    expected_tvl = env_int("SOS_EXPECTED_TVL_CAP_SATS", 1_000_000_000_000)
    expected_deposit = env_int("SOS_EXPECTED_MAX_DEPOSIT_SATS", 100_000_000_000)

    report: dict[str, Any] = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "service": "sos-public-testnet-probe",
        "checks": {},
        "failures": [],
    }
    failures: list[str] = report["failures"]

    endpoints = {
        "landing": "https://soulofsatoshi.com",
        "wallet": "https://app.soulofsatoshi.com",
        "explorer": "https://explorer.soulofsatoshi.com",
    }
    https_results: dict[str, Any] = {}
    for name, url in endpoints.items():
        try:
            https_results[name] = check_https(url, timeout)
        except ProbeError as exc:
            https_results[name] = {"status": "critical", "error": str(exc)}
            failures.append(f"https.{name}: {exc}")
    report["checks"]["https"] = https_results

    try:
        genesis_bytes = request_bytes(genesis_url, timeout)
        genesis_sha256 = hashlib.sha256(genesis_bytes).hexdigest()
        if genesis_sha256 != expected_genesis_sha256:
            raise ProbeError(
                f"genesis SHA-256 {genesis_sha256} != {expected_genesis_sha256}"
            )
        genesis = json.loads(genesis_bytes.decode("utf-8"))
        if not isinstance(genesis, dict):
            raise ProbeError("genesis root is not an object")
        if genesis.get("chain_id") != "0x534F53":
            raise ProbeError(f"unexpected genesis chain_id {genesis.get('chain_id')!r}")
        validators = genesis.get("initial_validators")
        if not isinstance(validators, list) or len(validators) != expected_genesis_validators:
            raise ProbeError(
                "unexpected genesis validator count: "
                f"{len(validators) if isinstance(validators, list) else 'invalid'}"
            )
        report["checks"]["genesis"] = {
            "status": "ok",
            "url": genesis_url,
            "sha256": genesis_sha256,
            "bytes": len(genesis_bytes),
            "chainId": genesis["chain_id"],
            "validators": len(validators),
        }
    except (ProbeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        failures.append(f"genesis: {exc}")
        report["checks"]["genesis"] = {"status": "critical", "error": str(exc)}

    try:
        latest = rpc(sos_rpc, "sos_getLatestBlock", [], timeout)
        height = as_int(latest["height"])
        block_hash = hex32(latest["hash"])
        if height <= 0:
            raise ProbeError(f"non-positive finalized height {height}")
        report["checks"]["chain"] = {
            "status": "ok",
            "height": height,
            "blockHash": block_hash,
        }
    except (KeyError, ProbeError, TypeError) as exc:
        failures.append(f"chain: {exc}")
        report["checks"]["chain"] = {"status": "critical", "error": str(exc)}
        height = None

    try:
        supply = rpc(sos_rpc, "sos_getSupplyInfo", [], timeout)
        expected = as_int(supply["expectedTotal"])
        actual = as_int(supply["actualTotal"])
        if supply.get("invariantOk") is not True or expected != actual:
            raise ProbeError(
                f"supply invariant failed: invariantOk={supply.get('invariantOk')!r}, "
                f"expected={expected}, actual={actual}"
            )
        report["checks"]["supply"] = {
            "status": "ok",
            "expectedTotal": expected,
            "actualTotal": actual,
        }
    except (KeyError, ProbeError, TypeError) as exc:
        failures.append(f"supply: {exc}")
        report["checks"]["supply"] = {"status": "critical", "error": str(exc)}

    try:
        privacy = rpc(sos_rpc, "sos_getPrivateInfo", [], timeout)
        if privacy.get("proofMode") != "ClientSTARK":
            raise ProbeError(f"unexpected proof mode {privacy.get('proofMode')!r}")
        report["checks"]["privacy"] = {
            "status": "ok",
            "proofMode": privacy["proofMode"],
            "commitments": as_int(privacy["commitmentCount"]),
            "nullifiers": as_int(privacy["nullifierCount"]),
            "treeRoot": hex32(privacy["treeRoot"]),
        }
    except (KeyError, ProbeError, TypeError) as exc:
        failures.append(f"privacy: {exc}")
        report["checks"]["privacy"] = {"status": "critical", "error": str(exc)}

    try:
        bridge = rpc(sos_rpc, "sos_getBridgeInfo", [], timeout)
        locked = as_int(bridge["totalLocked"])
        cap = as_int(bridge["tvlCap"])
        max_deposit = as_int(bridge["maxDeposit"])
        supply_locked = as_int(bridge["bridgeSupplyLocked"])
        if cap != expected_tvl or max_deposit != expected_deposit:
            raise ProbeError(
                f"unexpected caps: tvl={cap}, maxDeposit={max_deposit}"
            )
        if locked > cap or supply_locked != locked:
            raise ProbeError(
                f"bridge accounting mismatch: locked={locked}, "
                f"supplyLocked={supply_locked}, cap={cap}"
            )
        report["checks"]["bridge"] = {
            "status": "ok",
            "totalLocked": locked,
            "tvlCap": cap,
            "maxDeposit": max_deposit,
            "completedWithdrawals": as_int(bridge["completedWithdrawals"]),
        }
    except (KeyError, ProbeError, TypeError) as exc:
        failures.append(f"bridge: {exc}")
        report["checks"]["bridge"] = {"status": "critical", "error": str(exc)}

    try:
        dev = rpc_raw(sos_rpc, "sos_devCreditBalance", [], timeout)
        error = dev.get("error")
        if not isinstance(error, dict) or as_int(error.get("code")) != -32601:
            raise ProbeError(f"dev RPC was not rejected with -32601: {dev!r}")
        report["checks"]["devRpc"] = {
            "status": "ok",
            "errorCode": -32601,
        }
    except (ProbeError, TypeError) as exc:
        failures.append(f"devRpc: {exc}")
        report["checks"]["devRpc"] = {"status": "critical", "error": str(exc)}

    if height is not None:
        try:
            proof = rpc(sos_rpc, "sos_getBlockConsensusProof", [height], timeout)
            sos_valset = hex32(
                proof.get("validatorSetHash", proof.get("validator_set_hash"))
            )
            sos_epoch = as_int(proof["epoch"])
            contract_code = rpc(
                eth_rpc, "eth_getCode", [bridge_contract, "latest"], timeout
            )
            if not isinstance(contract_code, str) or contract_code in ("0x", "0x0"):
                raise ProbeError("bridge contract has no Ethereum bytecode")
            contract_raw = rpc(
                eth_rpc,
                "eth_call",
                [{"to": bridge_contract, "data": "0xcdea2912"}, "latest"],
                timeout,
            )
            contract_valset = hex32(contract_raw)
            if sos_valset != contract_valset:
                raise ProbeError(
                    f"validator-set mismatch: SOS={sos_valset}, Ethereum={contract_valset}"
                )
            report["checks"]["validatorSet"] = {
                "status": "ok",
                "sosHeight": height,
                "sosEpoch": sos_epoch,
                "sosHash": sos_valset,
                "ethereumHash": contract_valset,
                "contract": bridge_contract,
            }
        except (KeyError, ProbeError, TypeError) as exc:
            failures.append(f"validatorSet: {exc}")
            report["checks"]["validatorSet"] = {
                "status": "critical",
                "error": str(exc),
            }

    report["overallStatus"] = "ok" if not failures else "critical"
    return report


def self_test() -> None:
    assert as_int("42") == 42
    assert as_int("0x2a") == 42
    assert hex32("ab" * 32) == "0x" + "ab" * 32
    for bad in ("0x12", "zz" * 32, None):
        try:
            hex32(bad)
        except ProbeError:
            pass
        else:
            raise AssertionError(f"hex32 accepted {bad!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("sos-public-probe self-test: PASS")
        return 0
    report = run_probe()
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["overallStatus"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
