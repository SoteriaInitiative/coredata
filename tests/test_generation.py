import os
import sys
import random
from collections import defaultdict
from datetime import datetime
from lxml import etree

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
    assert len(ibans) == len(set(ibans))


def test_address_consistency():
    parties, receivers, accounts_by_bank = _generate_sample()
    for pid, p in parties.items():
        addr = p['address']
        recv = receivers[pid]
        assert recv['address'] == addr
        if recv['type'] == 'person':
            assert recv['last_name'] != 'Unknown'
            if p['type'] == 'person':
                assert recv['first_name'] != p['first_name']
                assert recv['last_name'] != p['last_name']
                assert recv['birthdate'] != p['birthdate']
        for bank_accounts in accounts_by_bank.values():
            if pid in bank_accounts:
                assert bank_accounts[pid]['address'] == addr


def test_entity_presence():
    parties, receivers, _ = _generate_sample()
    assert any(p['type'] == 'entity' for p in parties.values())
    assert any(r['type'] == 'entity' for r in receivers.values())


def test_receiver_account_details():
    parties, receivers, accounts_by_bank = _generate_sample()
    for recv in receivers.values():
        for acc in recv['accounts'].values():
            assert acc['bank_name'].startswith('Bank_')
            assert acc['iban'].startswith('CH')


def test_entity_legal_form_codes():
    addr = {
        'address': 'Teststrasse 1',
        'city': 'Zurich',
        'country_code': 'CH',
        'state': 'ZH',
    }
    ent = etree.Element('entity')
    generate_goaml._build_entity(ent, 'Example AG', 'AG', addr)
    assert ent.findtext('incorporation_legal_form') == generate_goaml.LEGAL_FORM_CODES['AG']


def test_account_balance_and_receiver_address():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, stats = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=0.5, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    sums = defaultdict(float)
    ts_per_account = defaultdict(list)
    running = {}
    acc_init = {acc['account_id']: acc['initial_balance'] for acc in accounts.values()}
    for tx in txs:
        tdata = tx['Transaction']
        acc = tdata['account']
        amt = tdata['currency_amount']
        acc_id = acc['account_id']
        sums[acc_id] += amt
        ts_per_account[acc_id].append(tdata['timestamp'])
        running.setdefault(acc_id, acc_init[acc_id])
        running[acc_id] += amt
        assert abs(round(running[acc_id], 2) - round(acc['balance_after'], 2)) <= 0.031
        ben = tdata['beneficiary']
        assert ben['address'] == acc['address']
        if ben['type'] == 'person':
            assert ben['last_name'] != 'Unknown'

    tx_acc_ids = {t['Transaction']['account']['account_id'] for t in txs}
    for acc in accounts.values():
        if acc['account_id'] not in tx_acc_ids:
            continue
        expected = round(acc_init[acc['account_id']] + sums.get(acc['account_id'], 0.0), 2)
        assert abs(acc['balance_after'] - expected) <= 0.031
    for acc_id, tlist in ts_per_account.items():
        assert tlist == sorted(tlist)
        assert len(tlist) == len(set(tlist))


def test_large_cash_local_label():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=1.0, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    threshold = 1000 + 2.0 * 200
    for tx in txs:
        if not tx['Transaction']['scenario']:
            continue
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


def test_generated_reports_validate():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1,
        accounts,
        receivers,
        parties,
        num_transactions=100,
        days_back=30,
        scenario_prob=0.5,
        bank_knows=True,
        std_multiplier=2.0,
        max_splits=3,
    )
    grouped = generate_goaml.group_by_party(txs)
    checked = 0
    for (originator, day), group in grouped.items():
        report = generate_goaml.build_report(1, originator, day, group, 'CHF')
        generate_goaml.validate_report(report)
        checked += 1
        if checked >= 3:
            break


def test_group_by_party_collects_all_same_day_transactions():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=0.5, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    grouped = generate_goaml.group_by_party(txs)
    for (originator, day), tx_list in grouped.items():
        count_in_all = sum(
            1
            for t in txs
            if t['Transaction']['transaction_originator'] == originator
            and datetime.utcfromtimestamp(t['Transaction']['timestamp'] / 1000).strftime('%Y-%m-%d') == day
        )
        assert len(tx_list) == count_in_all


def test_account_balance_invariant():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=0.5, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    acc_map = {acc['account_id']: acc for acc in accounts.values()}
    totals = defaultdict(float)
    for tx in txs:
        amt = tx['Transaction']['currency_amount']
        acc_id = tx['Transaction']['account']['account_id']
        totals[acc_id] += amt
    for acc_id, acc in acc_map.items():
        diff = acc['balance_after'] - acc['initial_balance']
        assert abs(round(diff, 2) - round(totals.get(acc_id, 0.0), 2)) <= 0.021


def test_report_validates_against_xsd():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=0.5, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    grouped = generate_goaml.group_by_party(txs)
    (originator, day), tx_list = next(iter(grouped.items()))
    report = generate_goaml.build_report(1, originator, day, tx_list, 'CHF')
    generate_goaml.validate_report(report)


def test_beneficial_owner_invariant():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=0.5, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    checked = set()
    for tx in txs:
        pid = tx['Transaction']['beneficiary_id']
        if pid in checked:
            continue
        originator = tx['Transaction']['transaction_originator']
        day = datetime.utcfromtimestamp(tx['Transaction']['timestamp'] / 1000).strftime('%Y-%m-%d')
        report = generate_goaml.build_report(1, originator, day, [tx], 'CHF')
        acc_el = report.find('.//t_to_my_client/to_account')
        client_num = acc_el.findtext('client_number')
        assert client_num != '000000'

        roles = [el.text for el in acc_el.findall('related_persons/account_related_person/role')]
        assert roles.count('13') == 1
        checked.add(pid)


def test_multibank_global_label():
    random.seed(0)
    generate_goaml.fake.seed_instance(0)
    parties, receivers, accounts_by_bank, _ = generate_goaml.generate_parties(
        num_parties=1, banks=2, multi_bank_prob=1.0, multi_bank_distribution=2
    )
    accounts1 = accounts_by_bank[1]
    accounts2 = accounts_by_bank[2]
    txs1, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts1, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=1.0, bank_knows=False, std_multiplier=2.0, max_splits=3
    )
    txs2, _ = generate_goaml.generate_transactions_for_bank(
        2, accounts2, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=1.0, bank_knows=False, std_multiplier=2.0, max_splits=3
    )
    bank_txs = {1: txs1, 2: txs2}
    generate_goaml.apply_global_labels(bank_txs)
    for b_id, txs in bank_txs.items():
        acc_ids = {acc['account_id'] for acc in accounts_by_bank[b_id].values()}
        assert acc_ids.issubset({t['Transaction']['account']['account_id'] for t in txs})
    for tx in txs1 + txs2:
        if tx['Transaction']['scenario']:
            assert tx['Transaction']['global_label'] == 1

    txs1b, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts1, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=1.0, bank_knows=False, std_multiplier=2.0, max_splits=3
    )
    txs2b, _ = generate_goaml.generate_transactions_for_bank(
        2, accounts2, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=0.0, bank_knows=False, std_multiplier=2.0, max_splits=3
    )
    bank_txs2 = {1: txs1b, 2: txs2b}
    generate_goaml.apply_global_labels(bank_txs2)
    for tx in txs1b:
        if tx['Transaction']['scenario']:
            assert tx['Transaction']['global_label'] == 0


def test_cross_bank_same_day():
    random.seed(0)
    generate_goaml.fake.seed_instance(0)
    parties, receivers, accounts_by_bank, multi_parties = generate_goaml.generate_parties(
        num_parties=1, banks=3, multi_bank_prob=1.0, multi_bank_distribution=3
    )
    events = generate_goaml.schedule_multi_bank_transactions(
        accounts_by_bank, receivers, parties, multi_parties, days_back=30, std_multiplier=2.0
    )
    bank_txs = {}
    for bank_id in range(1, 4):
        txs, _ = generate_goaml.generate_transactions_for_bank(
            bank_id,
            accounts_by_bank[bank_id],
            receivers,
            parties,
            num_transactions=100,
            days_back=30,
            scenario_prob=0.0,
            bank_knows=True,
            std_multiplier=2.0,
            max_splits=3,
            preseeded=events.get(bank_id, []),
        )
        bank_txs[bank_id] = txs
    pid = multi_parties[0]
    dates = []
    for bank_id in range(1, 4):
        tx = next(
            t for t in bank_txs[bank_id] if t['Transaction']['transaction_originator'] == pid and t['Transaction']['scenario']
        )
        day = datetime.utcfromtimestamp(tx['Transaction']['timestamp'] / 1000).date()
        dates.append(day)
    assert all(d == dates[0] for d in dates)
