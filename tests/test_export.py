import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from implementation import go_aml_export


def test_group_by_party_collects_all_same_day_transactions():
    data = go_aml_export.load_transactions('example/Bank_1_transactions.json')
    sar = go_aml_export.filter_sar_transactions(data)
    grouped = go_aml_export.group_by_party(sar, data)
    for (originator, day), txs in grouped.items():
        count_in_all = sum(
            1
            for t in data
            if t['Transaction']['transaction_originator'] == originator
            and datetime.utcfromtimestamp(t['Transaction']['timestamp'] / 1000).strftime('%Y-%m-%d') == day
        )
        assert len(txs) == count_in_all
