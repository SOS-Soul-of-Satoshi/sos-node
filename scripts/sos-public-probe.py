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
LIFECYCLE_HEX20 = re.compile(r"^[0-9a-f]{40}$")
LIFECYCLE_HEX32 = re.compile(r"^[0-9a-f]{64}$")
MAX_LIFECYCLE_RECORDS = 4096
MAX_LIFECYCLE_FUTURE_SKEW_MS = 30_000
READ_ONLY_RPC_METHODS = {
    "eth_call",
    "eth_getCode",
    "sos_devCreditBalance",
    "sos_getBlockConsensusProof",
    "sos_getBridgeInfo",
    "sos_getLatestBlock",
    "sos_getPrivateInfo",
    "sos_getSupplyInfo",
}
CANONICAL_BATCH_IMAGE_ID = (
    "0xba49fa2641bb0e1ded53525b20311645ec03218f2184b88c5cc941eb87e58db0"
)
CANONICAL_VALSET_IMAGE_ID = (
    "0x782999f999d1678e5b6fe9db05ef5a719e6af116bcf68929bd980e893f3715b1"
)


class ProbeError(RuntimeError):
    pass


class RetryableRequestError(ProbeError):
    pass


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None else int(value)


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProbeError(f"{name} is required for a release-bound public probe")
    return value


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


def abi_address(value: Any) -> str:
    if not isinstance(value, str):
        raise ProbeError("expected an ABI-encoded address")
    raw = value.removeprefix("0x").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", raw) or raw[:24] != "0" * 24:
        raise ProbeError(f"invalid ABI address: {value!r}")
    return "0x" + raw[-40:]


def abi_uint_tuple(value: Any, count: int) -> list[int]:
    if not isinstance(value, str):
        raise ProbeError("expected an ABI-encoded uint tuple")
    raw = value.removeprefix("0x")
    if not re.fullmatch(rf"[0-9a-fA-F]{{{64 * count}}}", raw):
        raise ProbeError(f"expected {count} ABI words, got {value!r}")
    return [int(raw[index : index + 64], 16) for index in range(0, len(raw), 64)]


def eth_call(rpc_url: str, contract: str, selector: str, timeout: float) -> Any:
    return rpc(
        rpc_url,
        "eth_call",
        [{"to": contract, "data": selector}, "latest"],
        timeout,
    )


def classify_validator_set(
    sos_hash: str, ethereum_hash: str, operations_enabled: bool | None
) -> tuple[str, str | None]:
    if sos_hash == ethereum_hash:
        return "ok", None
    detail = f"validator-set mismatch: SOS={sos_hash}, Ethereum={ethereum_hash}"
    if operations_enabled is False:
        return "paused", detail
    raise ProbeError(detail)


def overall_status(failures: list[str], warnings: list[str]) -> str:
    if failures:
        return "critical"
    return "degraded" if warnings else "ok"


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
    except urllib.error.HTTPError as exc:
        error_type = RetryableRequestError if exc.code in {502, 503, 504} else ProbeError
        raise error_type(f"request to {url} failed: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise RetryableRequestError(f"request to {url} failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProbeError(f"request to {url} returned invalid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ProbeError(f"{url} returned a non-object JSON response")
    return decoded


def rpc_raw(url: str, method: str, params: list[Any], timeout: float) -> dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    attempts = 2 if method in READ_ONLY_RPC_METHODS else 1
    for attempt in range(attempts):
        try:
            return request_json(url, payload, timeout)
        except RetryableRequestError:
            if attempt + 1 == attempts:
                raise
            time.sleep(0.2)
    raise AssertionError("RPC retry loop exhausted without returning or raising")


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


def lifecycle_exact_keys(
    value: Any, expected: set[str], label: str
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ProbeError(f"{label} has unsupported fields")
    return value


def lifecycle_integer(value: Any, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise ProbeError(f"{label} is invalid")
    return value


def lifecycle_age_seconds(
    generated_at_unix_ms: int,
    *,
    now_ms: int,
    max_age_seconds: int,
) -> float:
    if type(now_ms) is not int or now_ms <= 0:
        raise ProbeError("lifecycle comparison time is invalid")
    if type(max_age_seconds) is not int or max_age_seconds <= 0:
        raise ProbeError("lifecycle maximum age must be a positive integer")
    if generated_at_unix_ms > now_ms + MAX_LIFECYCLE_FUTURE_SKEW_MS:
        raise ProbeError("lifecycle generation time is too far in the future")
    age_ms = max(0, now_ms - generated_at_unix_ms)
    if age_ms > max_age_seconds * 1_000:
        raise ProbeError(
            f"lifecycle index is stale ({age_ms / 1_000:.1f}s old; "
            f"maximum {max_age_seconds}s)"
        )
    return round(age_ms / 1_000, 3)


def lifecycle_hex(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ProbeError(f"{label} is not canonical lowercase hex")
    return value


def lifecycle_sos_address(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(("sos1", "sost1"))
        or not 8 <= len(value) <= 128
        or not value.isascii()
        or not value.isalnum()
    ):
        raise ProbeError(f"{label} is not a bounded SOS address")
    return value


def lifecycle_transaction_hashes(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 32:
        raise ProbeError(f"{label} is invalid")
    hashes = [lifecycle_hex(item, LIFECYCLE_HEX32, label) for item in value]
    if len(hashes) != len(set(hashes)):
        raise ProbeError(f"{label} contains duplicates")
    return hashes


def validate_lifecycle_sos_transaction(value: Any, label: str) -> dict[str, Any]:
    transaction = lifecycle_exact_keys(
        value,
        {"txHash", "blockHeight", "blockHash", "appHash", "txIndex", "finalized"},
        label,
    )
    lifecycle_hex(transaction["txHash"], LIFECYCLE_HEX32, f"{label} transaction hash")
    lifecycle_hex(transaction["blockHash"], LIFECYCLE_HEX32, f"{label} block hash")
    lifecycle_hex(transaction["appHash"], LIFECYCLE_HEX32, f"{label} application hash")
    lifecycle_integer(transaction["blockHeight"], f"{label} block height")
    lifecycle_integer(transaction["txIndex"], f"{label} transaction index")
    if transaction["finalized"] is not True:
        raise ProbeError(f"{label} is not finalized")
    return transaction


def validate_lifecycle_eth_event(value: Any, label: str) -> dict[str, Any]:
    event = lifecycle_exact_keys(
        value,
        {"txHash", "blockNumber", "blockHash", "logIndex", "finalized"},
        label,
    )
    lifecycle_hex(event["txHash"], LIFECYCLE_HEX32, f"{label} transaction hash")
    lifecycle_hex(event["blockHash"], LIFECYCLE_HEX32, f"{label} block hash")
    lifecycle_integer(event["blockNumber"], f"{label} block number")
    lifecycle_integer(event["logIndex"], f"{label} log index")
    if event["finalized"] is not True:
        raise ProbeError(f"{label} is not finalized")
    return event


def validate_lifecycle_deposit(value: Any) -> str:
    deposit = lifecycle_exact_keys(
        value,
        {
            "lockId",
            "sosSender",
            "ownerAuthHash",
            "ethereumRecipient",
            "grossAmountSats",
            "relayFeeSats",
            "mintAmountSats",
            "status",
            "lock",
            "mintSubmissionTxHashes",
            "mint",
            "updatedAtUnixMs",
        },
        "deposit lifecycle record",
    )
    lock_id = lifecycle_hex(deposit["lockId"], LIFECYCLE_HEX32, "deposit lock id")
    lifecycle_sos_address(deposit["sosSender"], "deposit sender")
    lifecycle_hex(deposit["ownerAuthHash"], LIFECYCLE_HEX32, "deposit owner auth hash")
    lifecycle_hex(deposit["ethereumRecipient"], LIFECYCLE_HEX20, "deposit recipient")
    gross = lifecycle_integer(deposit["grossAmountSats"], "deposit gross amount", positive=True)
    fee = lifecycle_integer(deposit["relayFeeSats"], "deposit relay fee")
    mint_amount = lifecycle_integer(deposit["mintAmountSats"], "deposit mint amount", positive=True)
    if gross <= fee or gross - fee != mint_amount:
        raise ProbeError("deposit amounts are inconsistent")
    lifecycle_integer(deposit["updatedAtUnixMs"], "deposit update time", positive=True)
    lock = validate_lifecycle_sos_transaction(deposit["lock"], "deposit lock")
    submissions = lifecycle_transaction_hashes(
        deposit["mintSubmissionTxHashes"], "deposit submission transaction hash"
    )
    status = deposit["status"]
    if status not in {"locked", "mint-submitted", "minted"}:
        raise ProbeError("deposit lifecycle status is invalid")
    mint = deposit["mint"]
    if status == "locked" and (submissions or mint is not None):
        raise ProbeError("locked deposit contains mint evidence")
    if status == "mint-submitted" and (not submissions or mint is not None):
        raise ProbeError("submitted deposit evidence is incomplete")
    if status == "minted":
        finalized = lifecycle_exact_keys(
            mint,
            {
                "lockId",
                "ethereumRecipient",
                "mintAmountSats",
                "relayFeeSats",
                "sosBlockHeight",
                "event",
            },
            "finalized deposit event",
        )
        event = validate_lifecycle_eth_event(finalized["event"], "finalized deposit event")
        if (
            finalized["lockId"] != lock_id
            or finalized["ethereumRecipient"] != deposit["ethereumRecipient"]
            or finalized["mintAmountSats"] != mint_amount
            or finalized["relayFeeSats"] != fee
            or finalized["sosBlockHeight"] != lock["blockHeight"]
            or event["txHash"] not in submissions
        ):
            raise ProbeError("finalized deposit event conflicts with its lock")
    elif mint is not None:
        raise ProbeError("non-final deposit contains a finalized event")
    return lock_id


def validate_lifecycle_burn(value: Any) -> dict[str, Any]:
    burn = lifecycle_exact_keys(
        value,
        {"ethereumBurnIndex", "ethereumBurner", "amountSats", "sosRecipientHash", "event"},
        "finalized burn event",
    )
    lifecycle_integer(burn["ethereumBurnIndex"], "Ethereum burn index")
    lifecycle_hex(burn["ethereumBurner"], LIFECYCLE_HEX20, "Ethereum burner")
    lifecycle_integer(burn["amountSats"], "burn amount", positive=True)
    lifecycle_hex(burn["sosRecipientHash"], LIFECYCLE_HEX32, "burn recipient hash")
    validate_lifecycle_eth_event(burn["event"], "finalized burn event")
    return burn


def validate_lifecycle_withdrawal(value: Any) -> str:
    withdrawal = lifecycle_exact_keys(
        value,
        {
            "burnId",
            "ethereumBurnIndex",
            "ethereumBurner",
            "sosRecipient",
            "sosRecipientAuthHash",
            "sosRecipientHash",
            "burnAmountSats",
            "status",
            "burn",
            "releaseSubmissionTxHashes",
            "release",
            "updatedAtUnixMs",
        },
        "withdrawal lifecycle record",
    )
    burn_id = lifecycle_hex(withdrawal["burnId"], LIFECYCLE_HEX32, "withdrawal burn id")
    burn_index = lifecycle_integer(withdrawal["ethereumBurnIndex"], "withdrawal burn index")
    burner = lifecycle_hex(withdrawal["ethereumBurner"], LIFECYCLE_HEX20, "withdrawal burner")
    recipient = lifecycle_sos_address(withdrawal["sosRecipient"], "withdrawal recipient")
    lifecycle_hex(
        withdrawal["sosRecipientAuthHash"],
        LIFECYCLE_HEX32,
        "withdrawal recipient auth hash",
    )
    recipient_hash = lifecycle_hex(
        withdrawal["sosRecipientHash"], LIFECYCLE_HEX32, "withdrawal recipient hash"
    )
    if hashlib.sha256(recipient.encode("ascii")).hexdigest() != recipient_hash:
        raise ProbeError("withdrawal recipient does not match its burn hash")
    amount = lifecycle_integer(withdrawal["burnAmountSats"], "withdrawal amount", positive=True)
    lifecycle_integer(withdrawal["updatedAtUnixMs"], "withdrawal update time", positive=True)
    burn = validate_lifecycle_burn(withdrawal["burn"])
    if (
        burn["ethereumBurnIndex"] != burn_index
        or burn["ethereumBurner"] != burner
        or burn["sosRecipientHash"] != recipient_hash
        or burn["amountSats"] != amount
    ):
        raise ProbeError("finalized burn event conflicts with its withdrawal")
    submissions = lifecycle_transaction_hashes(
        withdrawal["releaseSubmissionTxHashes"], "release submission transaction hash"
    )
    status = withdrawal["status"]
    if status not in {"burn-observed", "release-submitted", "released"}:
        raise ProbeError("withdrawal lifecycle status is invalid")
    release = withdrawal["release"]
    if status == "burn-observed" and (submissions or release is not None):
        raise ProbeError("observed burn contains release evidence")
    if status == "release-submitted" and (not submissions or release is not None):
        raise ProbeError("submitted release evidence is incomplete")
    if status == "released":
        finalized = validate_lifecycle_sos_transaction(release, "finalized SOS release")
        if finalized["txHash"] not in submissions:
            raise ProbeError("finalized SOS release was not recorded as submitted")
    elif release is not None:
        raise ProbeError("non-final withdrawal contains finalized release evidence")
    return burn_id


def validate_lifecycle_index(
    lifecycle: Any,
    expected_sos_chain_id: int,
    expected_ethereum_chain_id: int,
    expected_bridge_domain: str,
    expected_contract: str,
    *,
    now_ms: int,
    max_age_seconds: int,
) -> dict[str, Any]:
    lifecycle = lifecycle_exact_keys(
        lifecycle,
        {
            "schema",
            "service",
            "generatedAtUnixMs",
            "sosChainId",
            "ethereumChainId",
            "bridgeDomain",
            "contractAddress",
            "deposits",
            "withdrawals",
        },
        "bridge lifecycle index",
    )
    if lifecycle["schema"] != "sos.bridge.lifecycle-index.v1":
        raise ProbeError(f"unexpected lifecycle schema {lifecycle['schema']!r}")
    if lifecycle["service"] != "sos-relayer-lifecycle":
        raise ProbeError(f"unexpected lifecycle service {lifecycle['service']!r}")
    if lifecycle_integer(lifecycle["sosChainId"], "lifecycle SOS chain id", positive=True) != expected_sos_chain_id:
        raise ProbeError("lifecycle SOS chain id does not match the deployment")
    if lifecycle_integer(
        lifecycle["ethereumChainId"], "lifecycle Ethereum chain id", positive=True
    ) != expected_ethereum_chain_id:
        raise ProbeError("lifecycle Ethereum chain id does not match the deployment")
    bridge_domain = lifecycle_hex(
        lifecycle["bridgeDomain"], LIFECYCLE_HEX32, "lifecycle bridge domain"
    )
    if hex32(bridge_domain) != expected_bridge_domain:
        raise ProbeError("lifecycle bridge domain does not match the deployment")
    contract = lifecycle_hex(
        lifecycle["contractAddress"], LIFECYCLE_HEX20, "lifecycle contract"
    )
    if contract != expected_contract.removeprefix("0x").lower():
        raise ProbeError("lifecycle contract does not match the deployment")

    deposits = lifecycle["deposits"]
    withdrawals = lifecycle["withdrawals"]
    if not isinstance(deposits, list) or not isinstance(withdrawals, list):
        raise ProbeError("lifecycle deposits/withdrawals are not arrays")
    if len(deposits) + len(withdrawals) > MAX_LIFECYCLE_RECORDS:
        raise ProbeError("lifecycle index contains too many records")
    deposit_ids = [validate_lifecycle_deposit(record) for record in deposits]
    withdrawal_ids = [validate_lifecycle_withdrawal(record) for record in withdrawals]
    if len(deposit_ids) != len(set(deposit_ids)):
        raise ProbeError("lifecycle index contains duplicate lock identifiers")
    if len(withdrawal_ids) != len(set(withdrawal_ids)):
        raise ProbeError("lifecycle index contains duplicate burn identifiers")

    generated_at = lifecycle_integer(
        lifecycle["generatedAtUnixMs"], "lifecycle generation time", positive=True
    )
    age_seconds = lifecycle_age_seconds(
        generated_at,
        now_ms=now_ms,
        max_age_seconds=max_age_seconds,
    )
    return {
        "status": "ok",
        "schema": lifecycle["schema"],
        "generatedAtUnixMs": generated_at,
        "ageSeconds": age_seconds,
        "deposits": len(deposits),
        "withdrawals": len(withdrawals),
        "bridgeDomain": expected_bridge_domain,
        "contract": expected_contract,
    }


def run_probe() -> dict[str, Any]:
    timeout = float(os.environ.get("SOS_PROBE_TIMEOUT_SECONDS", "15"))
    sos_rpc = os.environ.get("SOS_PUBLIC_RPC", "https://node.soulofsatoshi.com")
    genesis_url = os.environ.get(
        "SOS_PUBLIC_GENESIS_URL", "https://node.soulofsatoshi.com/genesis.json"
    )
    lifecycle_url = os.environ.get(
        "SOS_PUBLIC_LIFECYCLE_URL",
        "https://node.soulofsatoshi.com/bridge/lifecycle.json",
    )
    expected_genesis_sha256 = required_env("SOS_EXPECTED_GENESIS_SHA256").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_genesis_sha256):
        raise ProbeError("SOS_EXPECTED_GENESIS_SHA256 must be 32 bytes of hex")
    expected_genesis_validators = env_int("SOS_EXPECTED_GENESIS_VALIDATORS", 3)
    eth_rpc = os.environ.get(
        "SOS_ETH_RPC", "https://ethereum-sepolia-rpc.publicnode.com"
    )
    bridge_contract = required_env("SOS_BRIDGE_CONTRACT").lower()
    if not re.fullmatch(r"0x[0-9a-f]{40}", bridge_contract):
        raise ProbeError("SOS_BRIDGE_CONTRACT must be a 20-byte 0x-prefixed address")
    expected_bridge_domain = hex32(required_env("SOS_EXPECTED_BRIDGE_DOMAIN"))
    expected_tvl = env_int("SOS_EXPECTED_TVL_CAP_SATS", 1_000_000_000_000)
    expected_deposit = env_int("SOS_EXPECTED_MAX_DEPOSIT_SATS", 100_000_000_000)
    expected_batch_image_id = hex32(
        os.environ.get(
            "SOS_EXPECTED_BATCH_IMAGE_ID",
            CANONICAL_BATCH_IMAGE_ID,
        )
    )
    expected_valset_image_id = hex32(
        os.environ.get(
            "SOS_EXPECTED_VALSET_IMAGE_ID",
            CANONICAL_VALSET_IMAGE_ID,
        )
    )
    expected_chain_id = env_int("SOS_EXPECTED_CHAIN_ID", 5459795)
    expected_ethereum_chain_id = env_int("SOS_EXPECTED_ETHEREUM_CHAIN_ID", 11155111)
    lifecycle_max_age_seconds = env_int("SOS_LIFECYCLE_MAX_AGE_SECONDS", 180)
    if lifecycle_max_age_seconds <= 0:
        raise ProbeError("SOS_LIFECYCLE_MAX_AGE_SECONDS must be positive")

    report: dict[str, Any] = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "service": "sos-public-testnet-probe",
        "checks": {},
        "failures": [],
        "warnings": [],
    }
    failures: list[str] = report["failures"]
    warnings: list[str] = report["warnings"]

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
        lifecycle_bytes = request_bytes(lifecycle_url, timeout, limit=4_194_304)
        lifecycle = json.loads(lifecycle_bytes.decode("utf-8"))
        lifecycle_check = validate_lifecycle_index(
            lifecycle,
            expected_chain_id,
            expected_ethereum_chain_id,
            expected_bridge_domain,
            bridge_contract,
            now_ms=int(time.time() * 1_000),
            max_age_seconds=lifecycle_max_age_seconds,
        )
        lifecycle_check["url"] = lifecycle_url
        lifecycle_check["bytes"] = len(lifecycle_bytes)
        report["checks"]["bridgeLifecycle"] = lifecycle_check
    except (ProbeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        failures.append(f"bridgeLifecycle: {exc}")
        report["checks"]["bridgeLifecycle"] = {
            "status": "critical",
            "error": str(exc),
        }

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

    bridge_operations_enabled: bool | None = None
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
        bridge_operations_enabled = bridge.get("operationsEnabled")
        configured_operations_enabled = bridge.get("configuredOperationsEnabled")
        if not isinstance(bridge_operations_enabled, bool) or not isinstance(
            configured_operations_enabled, bool
        ):
            raise ProbeError("bridge operation flags are missing or non-boolean")
        if bridge_operations_enabled != configured_operations_enabled:
            raise ProbeError(
                "effective and configured bridge operation flags do not agree"
            )
        bridge_status = "ok" if bridge_operations_enabled else "paused"
        if not bridge_operations_enabled:
            warnings.append("bridge operations are administratively paused")
        report["checks"]["bridge"] = {
            "status": bridge_status,
            "totalLocked": locked,
            "tvlCap": cap,
            "maxDeposit": max_deposit,
            "completedWithdrawals": as_int(bridge["completedWithdrawals"]),
            "activeLocks": as_int(bridge["activeLocks"]),
            "operationsEnabled": bridge_operations_enabled,
            "configuredOperationsEnabled": configured_operations_enabled,
        }
    except (KeyError, ProbeError, TypeError) as exc:
        failures.append(f"bridge: {exc}")
        report["checks"]["bridge"] = {"status": "critical", "error": str(exc)}

    try:
        contract_code = rpc(eth_rpc, "eth_getCode", [bridge_contract, "latest"], timeout)
        if not isinstance(contract_code, str) or contract_code in ("0x", "0x0"):
            raise ProbeError("bridge contract has no Ethereum bytecode")
        batch_image_id = hex32(
            eth_call(eth_rpc, bridge_contract, "0x5fa7bfc5", timeout)
        )
        valset_image_id = hex32(
            eth_call(eth_rpc, bridge_contract, "0x395e0cd8", timeout)
        )
        bridge_domain = hex32(
            eth_call(eth_rpc, bridge_contract, "0x76ae5bc8", timeout)
        )
        contract_chain_id = as_int(
            eth_call(eth_rpc, bridge_contract, "0x866dc50c", timeout)
        )
        max_tvl, max_deposit, outstanding, available = abi_uint_tuple(
            eth_call(eth_rpc, bridge_contract, "0xc6dd812f", timeout), 4
        )
        wsos = abi_address(eth_call(eth_rpc, bridge_contract, "0x724d0223", timeout))
        wsos_bridge = abi_address(eth_call(eth_rpc, wsos, "0xe78cea92", timeout))
        wsos_supply = as_int(eth_call(eth_rpc, wsos, "0x18160ddd", timeout))
        matches = {
            "batchImageId": batch_image_id == expected_batch_image_id,
            "valsetImageId": valset_image_id == expected_valset_image_id,
            "bridgeDomain": bridge_domain == expected_bridge_domain,
            "chainId": contract_chain_id == expected_chain_id,
            "maxTvl": max_tvl == expected_tvl,
            "maxDeposit": max_deposit == expected_deposit,
            "availableAccounting": available == max_tvl - outstanding,
            "wsosBridge": wsos_bridge == bridge_contract,
            "wsosSupply": wsos_supply == outstanding,
        }
        if not all(matches.values()):
            raise ProbeError(f"bridge deployment invariant mismatch: {matches}")
        report["checks"]["bridgeContract"] = {
            "status": "ok",
            "contract": bridge_contract,
            "batchImageId": batch_image_id,
            "valsetTransitionImageId": valset_image_id,
            "bridgeDomain": bridge_domain,
            "chainId": contract_chain_id,
            "maxTvl": max_tvl,
            "maxDeposit": max_deposit,
            "outstandingTvl": outstanding,
            "availableTvl": available,
            "wsos": wsos,
            "wsosBridge": wsos_bridge,
            "wsosSupply": wsos_supply,
            "matches": matches,
        }
    except (ProbeError, TypeError, ValueError) as exc:
        failures.append(f"bridgeContract: {exc}")
        report["checks"]["bridgeContract"] = {
            "status": "critical",
            "error": str(exc),
        }

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
            contract_raw = eth_call(eth_rpc, bridge_contract, "0xcdea2912", timeout)
            contract_valset = hex32(contract_raw)
            status, detail = classify_validator_set(
                sos_valset, contract_valset, bridge_operations_enabled
            )
            if detail is not None:
                warnings.append(detail)
            report["checks"]["validatorSet"] = {
                "status": status,
                "sosHeight": height,
                "sosEpoch": sos_epoch,
                "sosHash": sos_valset,
                "ethereumHash": contract_valset,
                "contract": bridge_contract,
            }
            if detail is not None:
                report["checks"]["validatorSet"]["reason"] = detail
        except (KeyError, ProbeError, TypeError) as exc:
            failures.append(f"validatorSet: {exc}")
            report["checks"]["validatorSet"] = {
                "status": "critical",
                "error": str(exc),
            }

    report["overallStatus"] = overall_status(failures, warnings)
    return report


def self_test() -> None:
    assert "sos_getLatestBlock" in READ_ONLY_RPC_METHODS
    assert "sos_sendRawTransaction" not in READ_ONLY_RPC_METHODS
    assert as_int("42") == 42
    assert as_int("0x2a") == 42
    assert hex32("ab" * 32) == "0x" + "ab" * 32
    assert abi_address("0x" + "00" * 12 + "ab" * 20) == "0x" + "ab" * 20
    assert abi_uint_tuple("0x" + f"{1:064x}{2:064x}{3:064x}{4:064x}", 4) == [1, 2, 3, 4]
    assert classify_validator_set("0x01", "0x01", True) == ("ok", None)
    assert classify_validator_set("0x01", "0x02", False)[0] == "paused"
    assert overall_status([], []) == "ok"
    assert overall_status([], ["paused"]) == "degraded"
    assert overall_status(["failed"], ["paused"]) == "critical"
    recipient = "sost1testrecipient"
    recipient_hash = hashlib.sha256(recipient.encode("ascii")).hexdigest()
    lifecycle = {
        "schema": "sos.bridge.lifecycle-index.v1",
        "service": "sos-relayer-lifecycle",
        "generatedAtUnixMs": 1,
        "sosChainId": 5459795,
        "ethereumChainId": 11155111,
        "bridgeDomain": "11" * 32,
        "contractAddress": "22" * 20,
        "deposits": [
            {
                "lockId": "33" * 32,
                "sosSender": "sost1testsender",
                "ownerAuthHash": "55" * 32,
                "ethereumRecipient": "aa" * 20,
                "grossAmountSats": 100_000,
                "relayFeeSats": 1_000,
                "mintAmountSats": 99_000,
                "status": "minted",
                "lock": {
                    "txHash": "66" * 32,
                    "blockHeight": 10,
                    "blockHash": "77" * 32,
                    "appHash": "88" * 32,
                    "txIndex": 0,
                    "finalized": True,
                },
                "mintSubmissionTxHashes": ["99" * 32],
                "mint": {
                    "lockId": "33" * 32,
                    "ethereumRecipient": "aa" * 20,
                    "mintAmountSats": 99_000,
                    "relayFeeSats": 1_000,
                    "sosBlockHeight": 10,
                    "event": {
                        "txHash": "99" * 32,
                        "blockNumber": 100,
                        "blockHash": "ab" * 32,
                        "logIndex": 1,
                        "finalized": True,
                    },
                },
                "updatedAtUnixMs": 1,
            }
        ],
        "withdrawals": [
            {
                "burnId": "44" * 32,
                "ethereumBurnIndex": 7,
                "ethereumBurner": "bc" * 20,
                "sosRecipient": recipient,
                "sosRecipientAuthHash": "cd" * 32,
                "sosRecipientHash": recipient_hash,
                "burnAmountSats": 50_000,
                "status": "released",
                "burn": {
                    "ethereumBurnIndex": 7,
                    "ethereumBurner": "bc" * 20,
                    "amountSats": 50_000,
                    "sosRecipientHash": recipient_hash,
                    "event": {
                        "txHash": "de" * 32,
                        "blockNumber": 101,
                        "blockHash": "ef" * 32,
                        "logIndex": 2,
                        "finalized": True,
                    },
                },
                "releaseSubmissionTxHashes": ["12" * 32],
                "release": {
                    "txHash": "12" * 32,
                    "blockHeight": 11,
                    "blockHash": "13" * 32,
                    "appHash": "14" * 32,
                    "txIndex": 1,
                    "finalized": True,
                },
                "updatedAtUnixMs": 2,
            }
        ],
    }
    validated = validate_lifecycle_index(
        lifecycle,
        5459795,
        11155111,
        "0x" + "11" * 32,
        "0x" + "22" * 20,
        now_ms=1_000,
        max_age_seconds=10,
    )
    assert validated["deposits"] == 1
    assert validated["withdrawals"] == 1
    lifecycle["deposits"].append(lifecycle["deposits"][0])
    try:
        validate_lifecycle_index(
            lifecycle,
            5459795,
            11155111,
            "0x" + "11" * 32,
            "0x" + "22" * 20,
            now_ms=1_000,
            max_age_seconds=10,
        )
    except ProbeError:
        pass
    else:
        raise AssertionError("lifecycle accepted a duplicate lock id")
    lifecycle["deposits"].pop()
    lifecycle["withdrawals"][0]["release"]["finalized"] = False
    try:
        validate_lifecycle_index(
            lifecycle,
            5459795,
            11155111,
            "0x" + "11" * 32,
            "0x" + "22" * 20,
            now_ms=1_000,
            max_age_seconds=10,
        )
    except ProbeError:
        pass
    else:
        raise AssertionError("lifecycle accepted unfinalized release evidence")
    lifecycle["withdrawals"][0]["release"]["finalized"] = True
    try:
        validate_lifecycle_index(
            lifecycle,
            5459795,
            11155111,
            "0x" + "11" * 32,
            "0x" + "22" * 20,
            now_ms=20_000,
            max_age_seconds=10,
        )
    except ProbeError:
        pass
    else:
        raise AssertionError("lifecycle accepted a stale generation timestamp")
    lifecycle["generatedAtUnixMs"] = 40_001
    try:
        validate_lifecycle_index(
            lifecycle,
            5459795,
            11155111,
            "0x" + "11" * 32,
            "0x" + "22" * 20,
            now_ms=1_000,
            max_age_seconds=10,
        )
    except ProbeError:
        pass
    else:
        raise AssertionError("lifecycle accepted a far-future generation timestamp")
    try:
        classify_validator_set("0x01", "0x02", True)
    except ProbeError:
        pass
    else:
        raise AssertionError("open bridge accepted a validator-set mismatch")
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
    try:
        report = run_probe()
    except (ProbeError, TypeError, ValueError) as exc:
        report = {
            "schemaVersion": 1,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "service": "sos-public-testnet-probe",
            "overallStatus": "critical",
            "checks": {},
            "failures": [f"configuration: {exc}"],
            "warnings": [],
        }
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["overallStatus"] in ("ok", "degraded") else 1


if __name__ == "__main__":
    sys.exit(main())
