import os
import sys
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from implementation import go_aml_export


def test_group_by_party_collects_all_same_day_transactions():
    data = go_aml_export.load_transactions('example/Bank_1_transactions.json')
    grouped = go_aml_export.group_by_party(data)
    for (originator, day), txs in grouped.items():
        count_in_all = sum(
            1
            for t in data
            if t['Transaction']['transaction_originator'] == originator
            and datetime.utcfromtimestamp(t['Transaction']['timestamp'] / 1000).strftime('%Y-%m-%d') == day
        )
        assert len(txs) == count_in_all


def test_balance_updates_match_running_totals():
    data = go_aml_export.load_transactions('example/Bank_1_transactions.json')
    go_aml_export.update_account_balances(data)
    running = defaultdict(float)
    starts = {}
    for tx in sorted(data, key=lambda t: t['Transaction']['timestamp']):
        tdata = tx['Transaction']
        acc = tdata['account']
        aid = acc['account_id']
        if aid not in starts:
            starts[aid] = acc['balance_before']
            running[aid] = acc['balance_before']
        assert acc['balance_before'] == round(running[aid], 2)
        running[aid] += tdata['currency_amount']
        assert acc['balance_after'] == round(running[aid], 2)
