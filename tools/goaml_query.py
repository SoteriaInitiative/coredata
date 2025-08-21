"""Utility to query goAML style transaction data from a Google Cloud Storage bucket.

This module connects to the ``soteria-core-data`` bucket and loads the most recent
folder of generated data. It provides helper functions that perform common
queries on the goAML XML reports produced by the synthetic data generator. The
implementation intentionally avoids depending on ``pandas`` so that it can run in
minimal environments.

The queries implemented are:

1. List unique sending parties and entities
2. List unique receiving parties and entities
3. List related parties for a given counter-party
4. Retrieve all receiving transactions for a party across all banks
5. Retrieve all receiving transactions for a party for a specific bank
6. Retrieve transactions flagged by local/global labels

For convenience many command line parameters can also be provided via
environment variables:

``GCS_BUCKET_NAME``
    Name of the Google Cloud Storage bucket (defaults to ``soteria-core-data``).
``SENDER_NAME``
    Used by the ``receivers-for`` command when no positional argument is given.
``RECEIVER_NAME``
    Used by the ``senders-for`` command when no positional argument is given.
``PARTY_NAME``
    Used by the ``transactions`` command when no positional argument is given.
``BANK``
    Default bank identifier for the ``transactions`` command.
``START_BALANCE``
    Default starting balance for the ``transactions`` command.

Authentication with Google Cloud can also be configured via environment
variables when a JSON credentials file is not available:

``GCP_PROJECT_ID``
``GCP_PRIVATE_KEY_ID``
``GCP_PRIVATE_KEY``
``GCP_CLIENT_EMAIL``
``GCP_CLIENT_ID``

Run ``python tools/goaml_query.py --help`` for usage information.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from google.cloud import storage
from google.oauth2 import service_account
from lxml import etree


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


@dataclass
class LabeledTransaction:
    """Transaction enriched with local/global labels."""

    timestamp: datetime
    amount: float
    sender: str
    receiver: str
    bank: Optional[str]
    local_label: int
    global_label: int


# ---------------------------------------------------------------------------
# Loading data from Cloud Storage
# ---------------------------------------------------------------------------

def _get_storage_client() -> storage.Client:
    """Create a storage client using service-account fields from the environment."""

    project_id = os.getenv("GCP_PROJECT_ID")
    key_id = os.getenv("GCP_PRIVATE_KEY_ID")
    private_key = os.getenv("GCP_PRIVATE_KEY")
    client_email = os.getenv("GCP_CLIENT_EMAIL")
    client_id = os.getenv("GCP_CLIENT_ID")

    if all([project_id, key_id, private_key, client_email, client_id]):
        info = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": key_id,
            "private_key": private_key.replace("\\n", "\n"),
            "client_email": client_email,
            "client_id": client_id,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        creds = service_account.Credentials.from_service_account_info(info)
        return storage.Client(credentials=creds, project=project_id)

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


def load_transactions(prefix: Optional[str] = None) -> List[etree._Element]:
    """Load all transaction elements from goAML XML reports in the bucket."""

    client = _get_storage_client()
    bucket = client.bucket(_get_bucket_name())
    if prefix is None:
        prefix = _get_latest_prefix(bucket)
    transactions: List[etree._Element] = []
    for blob in bucket.list_blobs(prefix=prefix):
        if not blob.name.endswith(".xml"):
            continue
        root = etree.fromstring(blob.download_as_bytes())
        transactions.extend(root.findall("transaction"))
    return transactions


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _format_address_el(addr_el: Optional[etree._Element]) -> Optional[str]:
    if addr_el is None:
        return None
    parts = [
        addr_el.findtext("address"),
        addr_el.findtext("city"),
        addr_el.findtext("country_code"),
    ]
    return ", ".join([p for p in parts if p])


def _extract_party_from_person_el(
    person_el: Optional[etree._Element],
    *,
    bank: Optional[str] = None,
    iban: Optional[str] = None,
) -> Party:
    if person_el is None:
        return Party(name="Unknown", bank=bank, iban=iban)
    first = person_el.findtext("first_name", "").strip()
    last = person_el.findtext("last_name", "").strip()
    name = " ".join(part for part in [first, last] if part) or "Unknown"
    dob = person_el.findtext("birthdate")
    addr = _format_address_el(person_el.find("addresses/address"))
    return Party(name=name, dob=dob, bank=bank, address=addr, iban=iban)


def _extract_party_from_account_el(account_el: Optional[etree._Element]) -> Party:
    bank = iban = None
    person_el = None
    if account_el is not None:
        bank = account_el.findtext("institution_name") or account_el.findtext("swift")
        iban = account_el.findtext("iban")
        person_el = account_el.find("related_persons/account_related_person/t_person")
    return _extract_party_from_person_el(person_el, bank=bank, iban=iban)


def unique_parties(transactions: Iterable[etree._Element], role: str) -> List[Party]:
    """Return a list of unique parties for the given role."""

    parties: Dict[str, Party] = {}
    for tx in transactions:
        if role == "sending":
            acc_el = tx.find("t_from_my_client/from_account")
            party = _extract_party_from_account_el(acc_el)
        else:
            person_el = tx.find("t_to_my_client/to_person")
            bank = tx.findtext("t_to_my_client/to_account/institution_name")
            iban = tx.findtext("t_to_my_client/to_account/iban")
            party = _extract_party_from_person_el(person_el, bank=bank, iban=iban)
        parties[party.name] = party
    return list(parties.values())


def related_parties(transactions: Iterable[etree._Element], name: str, role: str) -> List[Party]:
    """Return unique counter-parties for ``name``.

    If ``role`` is ``sending`` the function returns receivers for that sender.
    If ``role`` is ``receiving`` the function returns the senders for that
    receiver.
    """

    results: Dict[str, Party] = {}
    for tx in transactions:
        sender = _extract_party_from_account_el(tx.find("t_from_my_client/from_account"))
        receiver = _extract_party_from_person_el(
            tx.find("t_to_my_client/to_person"),
            bank=tx.findtext("t_to_my_client/to_account/institution_name"),
            iban=tx.findtext("t_to_my_client/to_account/iban"),
        )
        if role == "sending" and sender.name == name:
            results[receiver.name] = receiver
        elif role == "receiving" and receiver.name == name:
            results[sender.name] = sender
    return list(results.values())


def receiving_transactions(
    transactions: Iterable[etree._Element],
    name: str,
    *,
    bank: Optional[str] = None,
    start_balance: float = 0.0,
) -> List[TransactionRecord]:
    """Return time sorted receiving transactions for ``name``."""

    records: List[TransactionRecord] = []
    balance = start_balance
    for tx in transactions:
        receiver = _extract_party_from_person_el(
            tx.find("t_to_my_client/to_person"),
            bank=tx.findtext("t_to_my_client/to_account/institution_name"),
            iban=tx.findtext("t_to_my_client/to_account/iban"),
        )
        if receiver.name != name:
            continue
        bank_id = receiver.bank
        if bank is not None and bank_id != bank:
            continue
        amount = float(tx.findtext("amount_local") or 0)
        balance += amount
        sender = _extract_party_from_account_el(tx.find("t_from_my_client/from_account"))
        ts_str = tx.findtext("date_transaction") or "1970-01-01T00:00:00"
        timestamp = datetime.fromisoformat(ts_str)
        record = TransactionRecord(
            timestamp=timestamp,
            amount=amount,
            sender=sender.name,
            receiver=receiver,
            bank=bank_id,
            balance_after=balance,
        )
        records.append(record)
    records.sort(key=lambda r: r.timestamp)
    return records


def _parse_labels(tx: etree._Element) -> Dict[str, int]:
    """Extract local and global label flags from a transaction element."""

    text = tx.findtext("comments", "")
    parts = dict(part.split("=", 1) for part in text.split(";") if "=" in part)
    return {
        "local_label": int(parts.get("local_label", "0")),
        "global_label": int(parts.get("global_label", "0")),
    }


def labelled_transactions(transactions: Iterable[etree._Element], scope: str) -> List[LabeledTransaction]:
    """Return transactions whose label flag is ``1`` for the given scope."""

    results: List[LabeledTransaction] = []
    for tx in transactions:
        labels = _parse_labels(tx)
        local = labels["local_label"]
        global_ = labels["global_label"]
        if scope == "local" and local != 1:
            continue
        if scope == "global" and global_ != 1:
            continue
        if scope == "both" and not (local == 1 and global_ == 1):
            continue

        sender = _extract_party_from_account_el(tx.find("t_from_my_client/from_account"))
        receiver = _extract_party_from_person_el(
            tx.find("t_to_my_client/to_person"),
            bank=tx.findtext("t_to_my_client/to_account/institution_name"),
            iban=tx.findtext("t_to_my_client/to_account/iban"),
        )
        amount = float(tx.findtext("amount_local") or 0)
        ts_str = tx.findtext("date_transaction") or "1970-01-01T00:00:00"
        timestamp = datetime.fromisoformat(ts_str)
        results.append(
            LabeledTransaction(
                timestamp=timestamp,
                amount=amount,
                sender=sender.name,
                receiver=receiver.name,
                bank=receiver.bank,
                local_label=local,
                global_label=global_,
            )
        )
    results.sort(key=lambda r: r.timestamp)
    return results


def _print_table(rows: List[Dict[str, Any]]) -> None:
    """Print ``rows`` as a simple table and append record count."""

    if not rows:
        print("No records found.")
        print("Total records: 0")
        return
    headers = list(rows[0].keys())
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row.get(h, ""))))
    header_row = " | ".join(f"{h:<{widths[h]}}" for h in headers)
    divider = "-+-".join("-" * widths[h] for h in headers)
    print(header_row)
    print(divider)
    for row in rows:
        print(" | ".join(f"{str(row.get(h, '')):<{widths[h]}}" for h in headers))
    print(f"Total records: {len(rows)}")


# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------

def _cmd_unique_parties(args: argparse.Namespace, role: str) -> None:
    txs = load_transactions()
    rows = [
        {
            "Name": p.name,
            "DOB": p.dob or "",
            "Bank": p.bank or "",
            "Address": p.address or "",
            "IBAN": p.iban or "",
        }
        for p in unique_parties(txs, role)
    ]
    _print_table(rows)


def _cmd_related(args: argparse.Namespace, role: str) -> None:
    if not args.name:
        raise SystemExit("A party name must be provided via argument or environment variable")
    txs = load_transactions()
    rows = [
        {
            "Name": p.name,
            "DOB": p.dob or "",
            "Bank": p.bank or "",
            "Address": p.address or "",
            "IBAN": p.iban or "",
        }
        for p in related_parties(txs, args.name, role)
    ]
    _print_table(rows)


def _cmd_transactions(args: argparse.Namespace) -> None:
    if not args.name:
        raise SystemExit("A party name must be provided via argument or environment variable")
    txs = load_transactions()
    records = receiving_transactions(
        txs,
        args.name,
        bank=args.bank,
        start_balance=args.start_balance,
    )
    rows = [
        {
            "Timestamp": r.timestamp.isoformat(),
            "Amount": f"{r.amount:.2f}",
            "Sender": r.sender,
            "Bank": r.bank or "",
            "Balance": f"{r.balance_after:.2f}" if r.balance_after is not None else "",
        }
        for r in records
    ]
    _print_table(rows)
    if records:
        print(f"Final balance: {records[-1].balance_after:.2f}")


def _cmd_labels(args: argparse.Namespace) -> None:
    txs = load_transactions()
    records = labelled_transactions(txs, args.scope)
    rows = [
        {
            "Timestamp": r.timestamp.isoformat(),
            "Amount": f"{r.amount:.2f}",
            "Sender": r.sender,
            "Receiver": r.receiver,
            "Bank": r.bank or "",
            "Local": r.local_label,
            "Global": r.global_label,
        }
        for r in records
    ]
    _print_table(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    senders = sub.add_parser("senders", help="List unique sending parties")
    senders.set_defaults(func=lambda a: _cmd_unique_parties(a, "sending"))

    receivers = sub.add_parser("receivers", help="List unique receiving parties")
    receivers.set_defaults(func=lambda a: _cmd_unique_parties(a, "receiving"))

    rec_for = sub.add_parser("receivers-for", help="Receivers for a given sender")
    rec_for.add_argument("name", nargs="?", default=os.getenv("SENDER_NAME"))
    rec_for.set_defaults(func=lambda a: _cmd_related(a, "sending"))

    send_for = sub.add_parser("senders-for", help="Senders for a given receiver")
    send_for.add_argument("name", nargs="?", default=os.getenv("RECEIVER_NAME"))
    send_for.set_defaults(func=lambda a: _cmd_related(a, "receiving"))

    tx_cmd = sub.add_parser("transactions", help="Show receiving transactions")
    tx_cmd.add_argument("name", nargs="?", default=os.getenv("PARTY_NAME"), help="Receiving party name")
    tx_cmd.add_argument("--bank", default=os.getenv("BANK"), help="Filter by bank identifier")
    tx_cmd.add_argument(
        "--start-balance",
        type=float,
        default=float(os.getenv("START_BALANCE", "0.0")),
        help="Starting balance used for cumulative calculation",
    )
    tx_cmd.set_defaults(func=_cmd_transactions)

    lbl_cmd = sub.add_parser("labels", help="Transactions with label flag equal to 1")
    lbl_cmd.add_argument(
        "--scope",
        choices=["local", "global", "both"],
        default="local",
        help="Select which label to filter by",
    )
    lbl_cmd.set_defaults(func=_cmd_labels)

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
