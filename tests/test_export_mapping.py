import random
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from implementation import generate_goaml, go_aml_export


def setup_module(module):
    random.seed(0)
    generate_goaml.fake.seed_instance(0)
    go_aml_export.fake.seed_instance(0)


def test_cash_deposit_structure():
    parties, receivers, accounts_by_bank, _ = generate_goaml.generate_parties(
        num_parties=10, banks=1, multi_bank_prob=0.0, multi_bank_distribution=1
    )
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=1.0, bank_knows=True, std_multiplier=2.0, max_splits=1
    )
    sar = [t for t in txs if t['Transaction']['local_label'] == 1]
    grouped = go_aml_export.group_by_party(sar, txs)
    originator, day = next(iter(grouped))
    report = go_aml_export.build_report(originator, day, grouped[(originator, day)], 'CHF')
    go_aml_export.validate_report(report)
    tx_el = report.find('transaction')
    t_from = tx_el.find('t_from_my_client')
    assert (t_from.find('from_person') is not None) ^ (t_from.find('from_entity') is not None)
    assert t_from.find('from_account') is None
    t_to = tx_el.find('t_to_my_client')
    to_account = t_to.find('to_account')
    assert to_account is not None
    assert to_account.findtext('iban')
    assert tx_el.findtext('transaction_description') == 'Cash Deposit'
    loc = tx_el.findtext('transaction_location')
    assert loc.startswith('ATM') or loc.startswith('Counter')
