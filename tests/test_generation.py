import os
import sys
import random
from collections import defaultdict
from datetime import datetime

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
    sums_sender = defaultdict(float)
    sums_receiver = defaultdict(float)
    ts_per_account = defaultdict(list)
    running = {}
    acc_init = {acc['account_id']: acc['initial_balance'] for acc in accounts.values()}
    recv_init = {recv['account']['account_id']: recv['account']['initial_balance'] for recv in receivers.values()}
    for tx in txs:
        tdata = tx['Transaction']
        s_acc = tdata['account']
        r_acc = tdata['beneficiary_account']
        amt = tdata['currency_amount']
        sums_sender[s_acc['account_id']] += amt
        sums_receiver[r_acc['account_id']] += amt
        ts_per_account[s_acc['account_id']].append(tdata['timestamp'])
        ts_per_account[r_acc['account_id']].append(tdata['timestamp'])
        running.setdefault(s_acc['account_id'], acc_init[s_acc['account_id']])
        running[s_acc['account_id']] += amt
        assert abs(round(running[s_acc['account_id']], 2) - round(s_acc['balance_after'], 2)) <= 0.021
        running.setdefault(r_acc['account_id'], recv_init[r_acc['account_id']])
        running[r_acc['account_id']] += amt
        assert abs(round(running[r_acc['account_id']], 2) - round(r_acc['balance_after'], 2)) <= 0.021
        ben = tdata['beneficiary']
        assert ben['address'] == r_acc['address']
        if ben['type'] == 'person':
            assert ben['last_name'] != 'Unknown'

    for acc in accounts.values():
        expected = round(acc_init[acc['account_id']] + sums_sender.get(acc['account_id'], 0.0), 2)
        assert abs(acc['balance_after'] - expected) <= 0.021
    for recv in receivers.values():
        r_acc = recv['account']
        expected = round(recv_init[r_acc['account_id']] + sums_receiver.get(r_acc['account_id'], 0.0), 2)
        assert abs(r_acc['balance_after'] - expected) <= 0.021
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
    for recv in receivers.values():
        acc_map[recv['account']['account_id']] = recv['account']
    totals = defaultdict(float)
    for tx in txs:
        amt = tx['Transaction']['currency_amount']
        totals[tx['Transaction']['account']['account_id']] += amt
        totals[tx['Transaction']['beneficiary_account']['account_id']] += amt
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


def test_lei_client_number_and_beneficial_owner():
    parties, receivers, accounts_by_bank = _generate_sample()
    accounts = accounts_by_bank[1]
    txs, _ = generate_goaml.generate_transactions_for_bank(
        1, accounts, receivers, parties, num_transactions=100, days_back=30,
        scenario_prob=0.5, bank_knows=True, std_multiplier=2.0, max_splits=3
    )
    # entity beneficiary transaction
    entity_tx = next(t for t in txs if t['Transaction']['beneficiary_account']['party_type'] == 'entity')
    originator = entity_tx['Transaction']['transaction_originator']
    day = datetime.utcfromtimestamp(entity_tx['Transaction']['timestamp'] / 1000).strftime('%Y-%m-%d')
    report_entity = generate_goaml.build_report(1, originator, day, [entity_tx], 'CHF')
    acc_el = report_entity.find('.//t_to_my_client/to_account')
    lei = acc_el.findtext('related_entities/account_related_entity/entity/incorporation_number')
    assert lei and len(lei) == 20
    name = acc_el.findtext('related_entities/account_related_entity/entity/name')
    assert any(form in name for form in generate_goaml.LEGAL_FORMS)
    client_num = acc_el.findtext('client_number')
    assert client_num != '000000'
    rel_person = acc_el.find('related_persons/account_related_person/t_person')
    assert rel_person.findtext('first_name') != 'Unknown'
    assert rel_person.findtext('last_name') != 'Unknown'
    assert rel_person.findtext('birthdate') != '1900-01-01T00:00:00'
    roles = [el.text for el in acc_el.findall('related_persons/account_related_person/role')]
    entity_rel = [el.text for el in acc_el.findall('related_entities/account_related_entity/account_entity_relation')]
    bo_count = sum(1 for r in roles if r in {'1', '2'}) + sum(1 for r in entity_rel if r in {'ACCCO'})
    assert bo_count == 1
    # person beneficiary transaction
    person_tx = next(t for t in txs if t['Transaction']['beneficiary_account']['party_type'] == 'person')
    originator_p = person_tx['Transaction']['transaction_originator']
    day_p = datetime.utcfromtimestamp(person_tx['Transaction']['timestamp'] / 1000).strftime('%Y-%m-%d')
    report_person = generate_goaml.build_report(1, originator_p, day_p, [person_tx], 'CHF')
    acc_person = report_person.find('.//t_to_my_client/to_account')
    client_num_p = acc_person.findtext('client_number')
    assert client_num_p != '000000'


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
