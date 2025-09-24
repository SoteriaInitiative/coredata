import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from soteria.coredata.goaml_query import build_parser, _get_storage_client


def test_env_defaults_receivers_for(monkeypatch):
    monkeypatch.setenv("SENDER_NAME", "Alice")
    parser = build_parser()
    args = parser.parse_args(["receivers-for"])
    assert args.name == "Alice"


def test_env_defaults_transactions(monkeypatch):
    monkeypatch.setenv("PARTY_FIRST_NAME", "Bob")
    monkeypatch.setenv("PARTY_LAST_NAME", "Receiver")
    monkeypatch.setenv("PARTY_DOB", "1980-02-02T00:00:00")
    monkeypatch.setenv("BANK", "BankA")
    monkeypatch.setenv("START_BALANCE", "10.5")
    parser = build_parser()
    args = parser.parse_args(["transactions"])
    assert args.first_name == "Bob"
    assert args.last_name == "Receiver"
    assert args.dob == "1980-02-02T00:00:00"
    assert args.bank == "BankA"
    assert args.start_balance == 10.5


def test_env_service_account(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "proj")
    monkeypatch.setenv("GCP_PRIVATE_KEY_ID", "kid")
    monkeypatch.setenv("GCP_PRIVATE_KEY", "dummy")
    monkeypatch.setenv("GCP_CLIENT_EMAIL", "svc@example.com")
    monkeypatch.setenv("GCP_CLIENT_ID", "cid")

    called = {}

    def fake_client(*args, **kwargs):
        called.update(kwargs)
        return object()

    dummy_creds = object()

    def fake_from_info(info):
        called["info"] = info
        return dummy_creds

    monkeypatch.setattr("soteria.coredata.goaml_query.storage.Client", fake_client)
    monkeypatch.setattr(
        "soteria.coredata.goaml_query.service_account.Credentials.from_service_account_info",
        fake_from_info,
    )

    _get_storage_client()

    assert called["project"] == "proj"
    assert called["credentials"] is dummy_creds
    assert called["info"]["private_key"] == "dummy"


def test_env_service_account_missing(monkeypatch):
    for var in (
        "GCP_PROJECT_ID",
        "GCP_PRIVATE_KEY_ID",
        "GCP_PRIVATE_KEY",
        "GCP_CLIENT_EMAIL",
        "GCP_CLIENT_ID",
    ):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(EnvironmentError):
        _get_storage_client()
