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
4. Retrieve all transactions for a party across all banks
5. Retrieve all transactions for a party for a specific bank
6. Retrieve transactions flagged by local/global labels
7. List parties that hold accounts at multiple banks

For convenience many command line parameters can also be provided via
environment variables:

``GCS_BUCKET_NAME``
    Name of the Google Cloud Storage bucket (defaults to ``soteria-core-data``).
``SENDER_NAME``
    Used by the ``receivers-for`` command when no positional argument is given.
``RECEIVER_NAME``
    Used by the ``senders-for`` command when no positional argument is given.
``PARTY_FIRST_NAME``
``PARTY_LAST_NAME``
``PARTY_DOB``
    Used by the ``transactions`` command when no positional arguments are given.
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
from typing import Any, Dict, Iterable, List, Optional, Tuple

from statistics import mean, median

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
    role: Optional[str] = None


@dataclass(frozen=True)
class PartyTxCounts:
    """A party enriched with transaction counts and account information."""

    party: Party
    incoming: int = 0
    outgoing: int = 0
    account_count: int = 0


@dataclass
class TransactionRecord:
    """Simplified view of a party transaction."""

    timestamp: datetime
    tx_amount: float
    balance_amount: Optional[float]
    counterparty: str
    direction: str  # "in" for incoming funds, "out" for outgoing
    bank: Optional[str]
    running_balance: Optional[float] = None
    local_label: int = 0
    global_label: int = 0


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


@dataclass(frozen=True)
class MultiBankParty:
    """Party that owns accounts at more than one bank."""

    party: Party
    banks: List[str]


# ---------------------------------------------------------------------------
# Loading data from Cloud Storage
# ---------------------------------------------------------------------------

def _get_storage_client() -> storage.Client:
    """Create a storage client using service-account fields from the environment.

    The helper requires the ``GCP_PROJECT_ID``, ``GCP_PRIVATE_KEY_ID``,
    ``GCP_PRIVATE_KEY``, ``GCP_CLIENT_EMAIL`` and ``GCP_CLIENT_ID`` variables to be
    defined.  This avoids relying on a JSON key file at runtime.
    """

    project_id = os.getenv("GCP_PROJECT_ID")
    key_id = os.getenv("GCP_PRIVATE_KEY_ID")
    private_key = os.getenv("GCP_PRIVATE_KEY")
    client_email = os.getenv("GCP_CLIENT_EMAIL")
    client_id = os.getenv("GCP_CLIENT_ID")

    missing = [
        var
        for var in (
            "GCP_PROJECT_ID",
            "GCP_PRIVATE_KEY_ID",
            "GCP_PRIVATE_KEY",
            "GCP_CLIENT_EMAIL",
            "GCP_CLIENT_ID",
        )
        if not os.getenv(var)
    ]
    if missing:
        raise EnvironmentError(
            "Missing required environment variables: " + ", ".join(missing)
        )

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


def _get_cache_dir() -> str:
    """Return the directory used for caching downloaded XML files."""

    return os.getenv("GOAML_CACHE_DIR", ".goaml_cache")


def load_transactions(prefix: Optional[str] = None) -> List[etree._Element]:
    """Load all transaction elements from goAML XML reports in the bucket.

    Downloaded XML files are cached locally so subsequent runs avoid repeated
    network calls.  Set the ``GOAML_CACHE_DIR`` environment variable to override
    the cache location.
    """

    cache_root = _get_cache_dir()
    os.makedirs(cache_root, exist_ok=True)

    # When a prefix is provided and cached, avoid hitting the network entirely.
    if prefix is not None:
        cache_dir = os.path.join(cache_root, prefix)
        if os.path.isdir(cache_dir):
            transactions: List[etree._Element] = []
            for name in os.listdir(cache_dir):
                if not name.endswith(".xml"):
                    continue
                path = os.path.join(cache_dir, name)
                root = etree.parse(path).getroot()
                transactions.extend(root.findall("transaction"))
            return transactions

    client: Optional[storage.Client] = None
    bucket: Optional[storage.Bucket] = None
    if prefix is None:
        client = _get_storage_client()
        bucket = client.bucket(_get_bucket_name())
        prefix = _get_latest_prefix(bucket)
    cache_dir = os.path.join(cache_root, prefix)
    if os.path.isdir(cache_dir):
        transactions: List[etree._Element] = []
        for name in os.listdir(cache_dir):
            if not name.endswith(".xml"):
                continue
            path = os.path.join(cache_dir, name)
            root = etree.parse(path).getroot()
            transactions.extend(root.findall("transaction"))
        return transactions

    if client is None:
        client = _get_storage_client()
        bucket = client.bucket(_get_bucket_name())

    os.makedirs(cache_dir, exist_ok=True)
    transactions: List[etree._Element] = []
    assert bucket is not None
    for blob in bucket.list_blobs(prefix=prefix):
        if not blob.name.endswith(".xml"):
            continue
        data = blob.download_as_bytes()
        filename = os.path.basename(blob.name)
        with open(os.path.join(cache_dir, filename), "wb") as fh:
            fh.write(data)
        root = etree.fromstring(data)
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


def _unwrap_person_el(person_el: Optional[etree._Element]) -> Optional[etree._Element]:
    """Return the underlying ``t_person`` element if wrapped in ``to_person``."""

    if person_el is None:
        return None
    if person_el.tag != "t_person":
        nested = person_el.find("t_person")
        if nested is not None:
            return nested
    return person_el


def _extract_party_from_person_el(
    person_el: Optional[etree._Element],
    *,
    bank: Optional[str] = None,
    iban: Optional[str] = None,
    role: Optional[str] = None,
) -> Party:
    person_el = _unwrap_person_el(person_el)
    if person_el is None:
        return Party(name="Unknown", bank=bank, iban=iban, role=role)
    first = person_el.findtext("first_name", "").strip()
    last = person_el.findtext("last_name", "").strip()
    name = " ".join(part for part in [first, last] if part) or "Unknown"
    dob = person_el.findtext("birthdate")
    addr = _format_address_el(person_el.find("addresses/address"))
    return Party(name=name, dob=dob, bank=bank, address=addr, iban=iban, role=role)


def _extract_party_from_entity_el(
    entity_el: Optional[etree._Element],
    *,
    bank: Optional[str] = None,
    iban: Optional[str] = None,
    role: Optional[str] = None,
) -> Party:
    if entity_el is None:
        return Party(name="Unknown", bank=bank, iban=iban, role=role)
    name = (
        entity_el.findtext("name")
        or entity_el.findtext("entity_name")
        or "Unknown"
    )
    dob = entity_el.findtext("incorporation_date")
    addr = _format_address_el(entity_el.find("addresses/address"))
    return Party(name=name, dob=dob, bank=bank, address=addr, iban=iban, role=role)


def _extract_party_from_account_el(account_el: Optional[etree._Element]) -> Party:
    bank = iban = None
    person_el = entity_el = None
    role = None
    if account_el is not None:
        bank = account_el.findtext("institution_name") or account_el.findtext("swift")
        iban = account_el.findtext("iban")
        rp = account_el.find("related_persons/account_related_person")
        if rp is not None:
            role = rp.findtext("role")
            person_el = rp.find("t_person")
            entity_el = rp.find("t_entity")
    if person_el is not None:
        return _extract_party_from_person_el(person_el, bank=bank, iban=iban, role=role)
    if entity_el is not None:
        return _extract_party_from_entity_el(entity_el, bank=bank, iban=iban, role=role)
    return Party(name="Unknown", bank=bank, iban=iban, role=role)


def _map_involved_parties(tx: etree._Element) -> Dict[str, Party]:
    """Map account IBANs to parties described in ``involved_parties``."""

    mapping: Dict[str, Party] = {}
    for party_el in tx.findall("involved_parties/party"):
        account_el = party_el.find("account_my_client")
        if account_el is None:
            account_el = party_el.find("account")
        if account_el is None:
            continue
        party = _extract_party_from_account_el(account_el)
        iban = account_el.findtext("iban")
        if iban:
            mapping[iban] = party
    return mapping


def _resolve_party_from_account(
    account_el: Optional[etree._Element], mapping: Dict[str, Party]
) -> Party:
    party = _extract_party_from_account_el(account_el)
    if (
        party.name == "Unknown"
        and account_el is not None
        and (iban := account_el.findtext("iban"))
        and iban in mapping
    ):
        mapped = mapping[iban]
        bank = account_el.findtext("institution_name") or account_el.findtext("swift") or mapped.bank
        return Party(
            name=mapped.name,
            dob=mapped.dob,
            bank=bank,
            address=mapped.address,
            iban=iban,
        )
    return party


def _extract_parties(tx: etree._Element) -> (Party, Party):
    """Return sender and receiver parties for a transaction."""

    mapping = _map_involved_parties(tx)

    from_acc = tx.find("t_from_my_client/from_account")
    if from_acc is not None:
        sender = _resolve_party_from_account(from_acc, mapping)
    else:
        sender = _extract_party_from_person_el(tx.find("t_from_my_client/from_person"))

    to_person = tx.find("t_to_my_client/to_person")
    if to_person is not None:
        bank = tx.findtext("t_to_my_client/to_account/institution_name")
        iban = tx.findtext("t_to_my_client/to_account/iban")
        receiver = _extract_party_from_person_el(to_person, bank=bank, iban=iban)
    else:
        receiver = _resolve_party_from_account(tx.find("t_to_my_client/to_account"), mapping)

    return sender, receiver


def unique_parties(
    transactions: Iterable[etree._Element], role: str
) -> List[PartyTxCounts]:
    """Return unique parties with transaction counts for the given role."""

    parties: Dict[str, Party] = {}
    counts: Dict[str, Dict[str, int]] = {}
    accounts: Dict[str, set[str]] = {}

    for tx in transactions:
        sender, receiver = _extract_parties(tx)
        parties[sender.name] = sender
        parties[receiver.name] = receiver

        counts.setdefault(sender.name, {"incoming": 0, "outgoing": 0})["outgoing"] += 1
        counts.setdefault(receiver.name, {"incoming": 0, "outgoing": 0})["incoming"] += 1

        if sender.iban:
            accounts.setdefault(sender.name, set()).add(sender.iban)
        if receiver.iban:
            accounts.setdefault(receiver.name, set()).add(receiver.iban)

    results: List[PartyTxCounts] = []
    for name, party in parties.items():
        incoming = counts.get(name, {}).get("incoming", 0)
        outgoing = counts.get(name, {}).get("outgoing", 0)
        if role == "sending" and outgoing == 0:
            continue
        if role == "receiving" and incoming == 0:
            continue
        account_count = len(accounts.get(name, set()))
        results.append(
            PartyTxCounts(
                party=party,
                incoming=incoming,
                outgoing=outgoing,
                account_count=account_count,
            )
        )
    return results


def multibank_parties(transactions: Iterable[etree._Element]) -> List[MultiBankParty]:
    """Return UBO parties that hold accounts at more than one bank."""

    mapping: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for tx in transactions:
        accounts = (
            tx.findall(".//from_account")
            + tx.findall(".//to_account")
            + tx.findall(".//account")
            + tx.findall(".//account_my_client")
        )
        for acc in accounts:
            bank = acc.findtext("institution_name") or acc.findtext("swift")
            for rel in acc.findall("related_persons/account_related_person"):
                role = rel.findtext("role")
                if role != "UBO":
                    continue
                person_el = rel.find("t_person")
                if person_el is not None:
                    party = _extract_party_from_person_el(person_el, bank=bank, role=role)
                else:
                    party = _extract_party_from_entity_el(rel.find("t_entity"), bank=bank, role=role)
                key = (party.name, party.dob or "", party.role or "")
                entry = mapping.setdefault(key, {"party": party, "banks": set()})
                if bank:
                    entry["banks"].add(bank)

    results: List[MultiBankParty] = []
    for data in mapping.values():
        banks = data["banks"]
        if len(banks) > 1:
            results.append(
                MultiBankParty(party=data["party"], banks=sorted(banks))
            )
    return results


def related_parties(transactions: Iterable[etree._Element], name: str, role: str) -> List[Party]:
    """Return unique counter-parties for ``name``.

    If ``role`` is ``sending`` the function returns receivers for that sender.
    If ``role`` is ``receiving`` the function returns the senders for that
    receiver.
    """

    results: Dict[str, Party] = {}
    for tx in transactions:
        sender, receiver = _extract_parties(tx)
        if role == "sending" and sender.name == name:
            results[receiver.name] = receiver
        elif role == "receiving" and receiver.name == name:
            results[sender.name] = sender
    return list(results.values())


def party_transactions(
    transactions: Iterable[etree._Element],
    first_name: str,
    last_name: str,
    dob: str,
    *,
    bank: Optional[str] = None,
    start_balance: float = 0.0,
) -> List[TransactionRecord]:
    """Return time sorted transactions for ``first_name``/``last_name``/``dob``.

    Both incoming and outgoing transactions are returned. Incoming amounts are
    added to the balance while outgoing amounts are subtracted.
    """

    records: List[TransactionRecord] = []
    target_name = f"{first_name} {last_name}".strip()
    for tx in transactions:
        labels = _parse_labels(tx)
        sender, receiver = _extract_parties(tx)
        amount = float(tx.findtext("amount_local") or 0)
        ts_str = tx.findtext("date_transaction") or "1970-01-01T00:00:00"
        timestamp = datetime.fromisoformat(ts_str)

        # Incoming
        if receiver.name == target_name and receiver.dob == dob:
            bank_id = receiver.bank
            if bank is not None and bank_id != bank:
                continue
            balance_amount = tx.findtext("t_to_my_client/to_account/balance")
            balance_amount = float(balance_amount) if balance_amount else None
            records.append(
                TransactionRecord(
                    timestamp=timestamp,
                    tx_amount=amount,
                    balance_amount=balance_amount,
                    counterparty=sender.name,
                    direction="in",
                    bank=bank_id,
                    local_label=labels["local_label"],
                    global_label=labels["global_label"],
                )
            )
            continue

        # Outgoing
        if sender.name == target_name and sender.dob == dob:
            bank_id = sender.bank
            if bank is not None and bank_id != bank:
                continue
            balance_amount = tx.findtext("t_from_my_client/from_account/balance")
            balance_amount = float(balance_amount) if balance_amount else None
            records.append(
                TransactionRecord(
                    timestamp=timestamp,
                    tx_amount=amount,
                    balance_amount=balance_amount,
                    counterparty=receiver.name,
                    direction="out",
                    bank=bank_id,
                    local_label=labels["local_label"],
                    global_label=labels["global_label"],
                )
            )

    records.sort(key=lambda r: r.timestamp)
    balance = start_balance
    for r in records:
        if r.direction == "in":
            balance += r.tx_amount
        else:
            balance -= r.tx_amount
        r.running_balance = balance
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

        sender, receiver = _extract_parties(tx)
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
            "Name": stats.party.name,
            "DOB": stats.party.dob or "",
            "Bank": stats.party.bank or "",
            "Address": stats.party.address or "",
            "IBAN": stats.party.iban or "",
            "Accounts": stats.account_count,
            "Incoming Tx": stats.incoming,
            "Outgoing Tx": stats.outgoing,
        }
        for stats in unique_parties(txs, role)
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
    if not (args.first_name and args.last_name and args.dob):
        raise SystemExit(
            "First name, last name and DOB must be provided via arguments or environment variables"
        )
    txs = load_transactions()
    records = party_transactions(
        txs,
        args.first_name,
        args.last_name,
        args.dob,
        bank=args.bank,
        start_balance=args.start_balance,
    )
    rows = [
        {
            "Timestamp": r.timestamp.isoformat(),
            "Tx Amount": f"{r.tx_amount:.2f}",
            "Balance Amount": f"{r.balance_amount:.2f}" if r.balance_amount is not None else "",
            "Running Balance": f"{r.running_balance:.2f}" if r.running_balance is not None else "",
            "Counterparty": r.counterparty,
            "Direction": r.direction,
            "Bank": r.bank or "",
            "Local Label": r.local_label,
            "Global Label": r.global_label,
        }
        for r in records
    ]
    _print_table(rows)
    if records:
        amounts = [r.tx_amount for r in records]
        print(f"Final balance: {records[-1].running_balance:.2f}")
        print(f"Average tx amount: {mean(amounts):.2f}")
        print(f"Median tx amount: {median(amounts):.2f}")


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


def _cmd_multibank(args: argparse.Namespace) -> None:
    txs = load_transactions()
    parties = multibank_parties(txs)
    rows = [
        {
            "Name": mb.party.name,
            "DOB": mb.party.dob or "",
            "Role": mb.party.role or "",
            "Banks": ", ".join(mb.banks),
            "Count": len(mb.banks),
        }
        for mb in parties
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

    tx_cmd = sub.add_parser("transactions", help="Show transactions for a party")
    tx_cmd.add_argument(
        "first_name",
        nargs="?",
        default=os.getenv("PARTY_FIRST_NAME"),
        help="Party first name",
    )
    tx_cmd.add_argument(
        "last_name",
        nargs="?",
        default=os.getenv("PARTY_LAST_NAME"),
        help="Party last name",
    )
    tx_cmd.add_argument(
        "dob",
        nargs="?",
        default=os.getenv("PARTY_DOB"),
        help="Party date of birth",
    )
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

    multi_cmd = sub.add_parser(
        "multi-bank", help="List parties with accounts at multiple banks"
    )
    multi_cmd.set_defaults(func=_cmd_multibank)

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
