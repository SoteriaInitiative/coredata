import copy
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from soteria.coredata import go_aml_export, generate_goaml


def _base_transaction():
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    originator = {
        'first_name': 'John',
        'last_name': 'Doe',
        'birthdate': '1980-01-01T00:00:00',
        'address': {
        'address': 'Main St 1',
        'city': 'Zurich',
        'country_code': generate_goaml.fake.current_country_code(),
        'state': 'ZH',

        },
    }
    account = {
        'account_id': 'A1',
        'bic': 'BIC1',
        'iban': 'CH9300000000000000001',
        'account_type': 'business',
        'country_code': 'CH',
        'first_name': 'Alice',
        'last_name': 'Smith',
        'birthdate': '1990-01-01T00:00:00',
        'address': {
        'address': 'Other St 2',
        'city': 'Bern',
        'country_code': generate_goaml.fake.current_country_code(),
        'state': 'BE',
        },
    }
    tx = {
        'Transaction': {
            'transaction_id': 'T1',
            'transaction_originator': 'P1',
            'transaction_type': 'CASH',
            'transaction_unit_type': 'cash',
            'currency_amount': 1000.0,
            'currency_code': 'CHF',
            'timestamp': now_ms,
            'account': account,
            'originator': originator,
            'local_label': 1,
            'global_label': 1,
        }
    }
    return tx


def test_same_person_probability_enforced():
    day = datetime.utcnow().strftime('%Y-%m-%d')
    base_tx = _base_transaction()
    txs = [copy.deepcopy(base_tx) for _ in range(100)]

    report_same = go_aml_export.build_report('P1', day, txs, 'CHF', same_person_prob=1.0)
    from_name = report_same.find(
        './/transaction/t_from_my_client/from_person/first_name'
    ).text
    to_name = report_same.find(
        './/transaction/t_to_my_client/to_account/related_persons/account_related_person/t_person/first_name'
    ).text
    assert from_name == to_name

    report_diff = go_aml_export.build_report('P1', day, txs, 'CHF', same_person_prob=0.0)
    from_name_diff = report_diff.find(
        './/transaction/t_from_my_client/from_person/first_name'
    ).text
    to_name_diff = report_diff.find(
        './/transaction/t_to_my_client/to_account/related_persons/account_related_person/t_person/first_name'
    ).text
    assert from_name_diff != to_name_diff
