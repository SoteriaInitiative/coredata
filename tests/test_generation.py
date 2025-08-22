import os
import sys
import random
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from implementation import generate_goaml


def setup_module(module):
    random.seed(0)
    generate_goaml.fake.seed_instance(0)


def _generate_sample():
    random.seed(0)
    generate_goaml.fake.seed_instance(0)
    parties, receivers, accounts_by_bank, _ = generate_goaml.generate_parties(
        num_parties=10, banks=2, multi_bank_prob=0.5, multi_bank_distribution=2
    )
    return parties, receivers, accounts_by_bank


def test_iban_uniqueness():
    parties, receivers, accounts_by_bank = _generate_sample()
    ibans = []
    for bank_accounts in accounts_by_bank.values():
        for acc in bank_accounts.values():
            ibans.append(acc['iban'])
    for recv in receivers.values():
        ibans.append(recv['account']['iban'])
    assert len(ibans) == len(set(ibans))


def test_address_consistency():
    parties, receivers, accounts_by_bank = _generate_sample()
    for pid, p in parties.items():
        addr = p['address']
        recv = receivers[pid]
        assert recv['address'] == addr
        if recv['type'] == 'person':
            assert recv['last_name'] == 'Unknown'
            if p['type'] == 'person':
                assert recv['first_name'] != p['first_name']
                assert recv['birthdate'] != p['birthdate']
        for bank_accounts in accounts_by_bank.values():
            if pid in bank_accounts:
                assert bank_accounts[pid]['address'] == addr


def test_receiver_account_details():
    parties, receivers, accounts_by_bank = _generate_sample()
    for recv in receivers.values():
        acc = recv['account']
        assert acc['bank_name'].startswith('Bank_')
        assert acc['iban'].startswith('CH')


def test_account_balance_and_receiver_address():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, stats = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=0.5, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    sums = defaultdict(float)
    for tx in txs:
        tdata = tx['Transaction']
        acc = tdata['account']
        sums[acc['account_id']] += tdata['currency_amount']
        ben = tdata['beneficiary']
        assert ben['address'] == acc['address']
        if ben['type'] == 'person':
            assert ben['last_name'] == 'Unknown'

    for acc in accounts.values():
        assert acc['balance_after'] == round(sums.get(acc['account_id'], 0.0), 2)


def test_large_cash_local_label():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=1.0, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    threshold = 1000 + 2.0 * 200
    for tx in txs:
        amt = tx['Transaction']['currency_amount']
        local = tx['Transaction']['local_label']
        if amt >= threshold:
            assert local == 1
        else:
            assert local == 0

    parties2, receivers2, accounts_by_bank2 = _generate_sample()
    accounts2 = accounts_by_bank2[1]
    txs2, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts2, receivers2, parties2, num_transactions=100, days_back=30,
        scenario_prob=1.0, bank_knows=False, std_multiplier=2.0, max_splits=3
    )
    for tx in txs2:
        assert tx['Transaction']['local_label'] == 0
