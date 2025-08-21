from tools.goaml_query import build_parser


def test_env_defaults_receivers_for(monkeypatch):
    monkeypatch.setenv("SENDER_NAME", "Alice")
    parser = build_parser()
    args = parser.parse_args(["receivers-for"])
    assert args.name == "Alice"


def test_env_defaults_transactions(monkeypatch):
    monkeypatch.setenv("PARTY_NAME", "Bob")
    monkeypatch.setenv("BANK", "BankA")
    monkeypatch.setenv("START_BALANCE", "10.5")
    parser = build_parser()
    args = parser.parse_args(["transactions"])
    assert args.name == "Bob"
    assert args.bank == "BankA"
    assert args.start_balance == 10.5
