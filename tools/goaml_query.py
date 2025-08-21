"""Utility to query goAML style transaction data from a Google Cloud Storage bucket.

This module connects to the ``soteria-core-data`` bucket and loads the most recent
folder of generated data. It provides helper functions that perform common
queries on the JSON transactions produced by the synthetic data generator. The
implementation intentionally avoids depending on ``pandas`` so that it can run in
minimal environments.

The queries implemented are:

1. List unique sending parties and entities
2. List unique receiving parties and entities
3. List related parties for a given counter-party
4. Retrieve all receiving transactions for a party across all banks
5. Retrieve all receiving transactions for a party for a specific bank

Run ``python tools/goaml_query.py --help`` for usage information.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from google.cloud import storage


@dataclass(frozen=True)
class Party:
    """Representation of a party or entity involved in transactions."""

    name: str
    dob: Optional[str] = None
    bank: Optional[str] = None
    address: Optional[str] = None
    iban: Optional[str] = None


@dataclass
class TransactionRecord:
    """Simplified view of a transaction used for time sorted queries."""

    timestamp: datetime
    amount: float
    sender: str
    receiver: Party
    bank: Optional[str]
    balance_after: Optional[float] = None


# ---------------------------------------------------------------------------
# Loading data from Cloud Storage
# ---------------------------------------------------------------------------

def _get_storage_client() -> storage.Client:
    return storage.Client()


def _get_bucket_name() -> str:
    return os.getenv("GCS_BUCKET_NAME", "soteria-core-data")


def _get_latest_prefix(bucket: storage.Bucket) -> str:
    """Return the name of the most recently created top level folder."""

    folders: Dict[str, datetime] = {}
    for blob in bucket.list_blobs():
        parts = blob.name.split("/", 1)
        prefix = parts[0]
        created = blob.time_created
        prev = folders.get(prefix)
        if prev is None or created > prev:
            folders[prefix] = created
    if not folders:
        raise RuntimeError("No data folders found in bucket")
    return max(folders.items(), key=lambda item: item[1])[0]


def _download_json(bucket: storage.Bucket, blob_name: str) -> Iterable[dict]:
    data = json.loads(bucket.blob(blob_name).download_as_bytes())
    if isinstance(data, list):
        return data
    raise ValueError(f"Expected list in {blob_name}")


def load_transactions(prefix: Optional[str] = None) -> List[dict]:
    """Load all transaction JSON files from the latest folder in the bucket."""

    client = _get_storage_client()
    bucket = client.bucket(_get_bucket_name())
    if prefix is None:
        prefix = _get_latest_prefix(bucket)
    transactions: List[dict] = []
    for blob in bucket.list_blobs(prefix=prefix):
        if blob.name.endswith("_transactions.json"):
            transactions.extend(_download_json(bucket, blob.name))
    return transactions


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _format_address(addr: Optional[dict]) -> Optional[str]:
    if not isinstance(addr, dict):
        return addr
    parts = [addr.get("address"), addr.get("city"), addr.get("country_code")]
    return ", ".join([p for p in parts if p])


def _extract_party_from_account(account: dict, name: str) -> Party:
    address = account.get("address")
    if isinstance(address, dict):
        address = _format_address(address)
    return Party(
        name=name,
        dob=account.get("birthdate"),
        bank=account.get("bank_name") or account.get("bic"),
        address=address,
        iban=account.get("iban"),
    )


def unique_parties(transactions: Iterable[dict], role: str) -> List[Party]:
    """Return a list of unique parties for the given role."""

    parties: Dict[str, Party] = {}
    for tx in transactions:
        tdata = tx.get("Transaction", {})
        account = tdata.get("account", {})
        if account.get("transaction_role") != role:
            continue
        if role == "sending":
            name = tdata.get("transaction_originator", "Unknown")
        else:
            ben = tdata.get("beneficiary")
            if isinstance(ben, dict):
                first = ben.get("first_name", "").strip()
                last = ben.get("last_name", "").strip()
                name = " ".join(part for part in [first, last] if part)
            else:
                name = tdata.get("transaction_beneficiary", "Unknown")
        parties[name] = _extract_party_from_account(account, name)
    return list(parties.values())


def related_parties(transactions: Iterable[dict], name: str, role: str) -> List[Party]:
    """Return unique counter-parties for ``name``.

    If ``role`` is ``sending`` the function returns receivers for that sender.
    If ``role`` is ``receiving`` the function returns the senders for that
    receiver.
    """

    results: Dict[str, Party] = {}
    for tx in transactions:
        tdata = tx.get("Transaction", {})
        account = tdata.get("account", {})
        sender_name = tdata.get("transaction_originator")
        receiver_name = tdata.get("transaction_beneficiary")
        if role == "sending" and sender_name == name:
            results[receiver_name] = _extract_party_from_account(account, receiver_name)
        elif role == "receiving" and receiver_name == name:
            results[sender_name] = _extract_party_from_account(account, sender_name)
    return list(results.values())


def receiving_transactions(
    transactions: Iterable[dict],
    name: str,
    *,
    bank: Optional[str] = None,
    start_balance: float = 0.0,
) -> List[TransactionRecord]:
    """Return time sorted receiving transactions for ``name``."""

    records: List[TransactionRecord] = []
    balance = start_balance
    for tx in transactions:
        tdata = tx.get("Transaction", {})
        account = tdata.get("account", {})
        if account.get("transaction_role") != "receiving":
            continue
        if tdata.get("transaction_beneficiary") != name:
            continue
        bank_id = account.get("bank_name") or account.get("bic")
        if bank is not None and bank_id != bank:
            continue
        amount = float(tdata.get("currency_amount", 0))
        balance += amount
        record = TransactionRecord(
            timestamp=datetime.utcfromtimestamp(tdata.get("timestamp", 0) / 1000.0),
            amount=amount,
            sender=tdata.get("transaction_originator", "Unknown"),
            receiver=_extract_party_from_account(account, name),
            bank=bank_id,
            balance_after=balance,
        )
        records.append(record)
    records.sort(key=lambda r: r.timestamp)
    return records


# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------

def _cmd_unique_parties(args: argparse.Namespace, role: str) -> None:
    txs = load_transactions()
    for party in unique_parties(txs, role):
        print(json.dumps(party.__dict__, indent=2))


def _cmd_related(args: argparse.Namespace, role: str) -> None:
    txs = load_transactions()
    for party in related_parties(txs, args.name, role):
        print(json.dumps(party.__dict__, indent=2))


def _cmd_transactions(args: argparse.Namespace) -> None:
    txs = load_transactions()
    records = receiving_transactions(
        txs,
        args.name,
        bank=args.bank,
        start_balance=args.start_balance,
    )
    for r in records:
        payload = {
            "timestamp": r.timestamp.isoformat(),
            "amount": r.amount,
            "sender": r.sender,
            "balance_after": r.balance_after,
            "bank": r.bank,
        }
        print(json.dumps(payload, indent=2))
    if records:
        print(f"Final balance: {records[-1].balance_after:.2f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    senders = sub.add_parser("senders", help="List unique sending parties")
    senders.set_defaults(func=lambda a: _cmd_unique_parties(a, "sending"))

    receivers = sub.add_parser("receivers", help="List unique receiving parties")
    receivers.set_defaults(func=lambda a: _cmd_unique_parties(a, "receiving"))

    rec_for = sub.add_parser("receivers-for", help="Receivers for a given sender")
    rec_for.add_argument("name")
    rec_for.set_defaults(func=lambda a: _cmd_related(a, "sending"))

    send_for = sub.add_parser("senders-for", help="Senders for a given receiver")
    send_for.add_argument("name")
    send_for.set_defaults(func=lambda a: _cmd_related(a, "receiving"))

    tx_cmd = sub.add_parser("transactions", help="Show receiving transactions")
    tx_cmd.add_argument("name", help="Receiving party name")
    tx_cmd.add_argument("--bank", help="Filter by bank identifier")
    tx_cmd.add_argument(
        "--start-balance",
        type=float,
        default=0.0,
        help="Starting balance used for cumulative calculation",
    )
    tx_cmd.set_defaults(func=_cmd_transactions)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
