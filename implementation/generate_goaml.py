import argparse
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta

from faker import Faker
from lxml import etree
import xmlschema

from google_storage_utils import gs_utils

# Constants and mappings
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'standard', 'XML_Schema.xsd')

TYPE_MAP = {
    'deposit': 'CASHT',
    'wire': 'B2BWT',
}

FUNDS_TYPE_MAP = {
    'cash': '26',
    'currency': '27',
}

ACCOUNT_TYPE_MAP = {
    'current': '1',
    'business': '2',
    'savings': '3',
    'investment': '14',
    'debit': '10',
}

fake = Faker()


def _build_address(parent, address):
    addr = etree.SubElement(parent, 'address')
    etree.SubElement(addr, 'address_type').text = '1'
    etree.SubElement(addr, 'address').text = address['address']
    etree.SubElement(addr, 'city').text = address['city']
    etree.SubElement(addr, 'country_code').text = address['country_code']
    etree.SubElement(addr, 'state').text = address['state']
    return addr


def _build_person(parent, first_name, last_name, address):
    etree.SubElement(parent, 'gender').text = 'U'
    etree.SubElement(parent, 'first_name').text = first_name
    etree.SubElement(parent, 'last_name').text = last_name
    etree.SubElement(parent, 'birthdate').text = '1900-01-01T00:00:00'
    etree.SubElement(parent, 'nationality1').text = 'CH'
    addresses = etree.SubElement(parent, 'addresses')
    _build_address(addresses, address)


def _build_account(parent, account, currency_code_local, day, tag):
    acc_el = etree.SubElement(parent, tag)
    etree.SubElement(acc_el, 'institution_name').text = account.get('bank_name', 'Dummy Bank')
    etree.SubElement(acc_el, 'swift').text = account.get('bic', 'DUMMYBIC')
    etree.SubElement(acc_el, 'branch').text = 'ZH'
    etree.SubElement(acc_el, 'account_category').text = 'ACCNT'
    etree.SubElement(acc_el, 'account').text = account.get('account_id', '000000')
    etree.SubElement(acc_el, 'currency_code').text = currency_code_local
    etree.SubElement(acc_el, 'iban').text = account.get('iban', 'CH9300762011623852957')
    etree.SubElement(acc_el, 'client_number').text = '000000'
    acc_type = ACCOUNT_TYPE_MAP.get(account.get('account_type', 'current'), '1')
    etree.SubElement(acc_el, 'account_type').text = acc_type
    related = etree.SubElement(acc_el, 'related_persons')
    arp = etree.SubElement(related, 'account_related_person')
    tp = etree.SubElement(arp, 't_person')
    addr = account.get('address', {'address': 'Unknown', 'city': 'Unknown', 'country_code': 'CH', 'state': 'ZH'})
    _build_person(tp, account.get('first_name', 'Unknown'), account.get('last_name', 'Unknown'), addr)
    etree.SubElement(arp, 'role').text = '1'
    rr = etree.SubElement(arp, 'relation_date_range')
    etree.SubElement(rr, 'valid_from').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'opened').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'balance').text = f"{account.get('balance_after', 0):.2f}"
    etree.SubElement(acc_el, 'date_balance').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'status_code').text = '1'
    etree.SubElement(acc_el, 'beneficiary_comment').text = ' '
    return acc_el


def build_report(bank_id, scenario, originator, day, transactions, currency_code_local):
    report = etree.Element('report')
    etree.SubElement(report, 'rentity_id').text = '1'
    etree.SubElement(report, 'rentity_branch').text = 'HO'
    etree.SubElement(report, 'submission_code').text = 'E'
    etree.SubElement(report, 'report_code').text = 'AIFT'
    etree.SubElement(report, 'entity_reference').text = 'DUMMY'
    etree.SubElement(report, 'fiu_ref_number').text = 'DUMMY'
    etree.SubElement(report, 'report_date').text = f'{day}T00:00:00'
    etree.SubElement(report, 'currency_code_local').text = currency_code_local

    location = etree.SubElement(report, 'location')
    etree.SubElement(location, 'address_type').text = '1'
    etree.SubElement(location, 'address').text = 'Unknown'
    etree.SubElement(location, 'city').text = 'Unknown'
    etree.SubElement(location, 'country_code').text = 'CH'
    etree.SubElement(location, 'state').text = 'ZH'

    etree.SubElement(report, 'reason')
    etree.SubElement(report, 'action')

    for tx in transactions:
        tdata = tx['Transaction']
        tx_el = etree.SubElement(report, 'transaction')
        etree.SubElement(tx_el, 'transactionnumber').text = tdata['transaction_id']
        etree.SubElement(tx_el, 'transaction_description').text = scenario
        date_str = datetime.utcfromtimestamp(tdata['timestamp'] / 1000).strftime('%Y-%m-%d')
        etree.SubElement(tx_el, 'date_transaction').text = f'{date_str}T00:00:00'
        etree.SubElement(tx_el, 'value_date').text = f'{date_str}T00:00:00'
        tx_code = TYPE_MAP.get(tdata.get('transaction_type', 'deposit'), 'CASHT')
        etree.SubElement(tx_el, 'transaction_type_code').text = tx_code
        etree.SubElement(tx_el, 'amount_local').text = f"{tdata.get('currency_amount', 0):.2f}"
        funds_code = FUNDS_TYPE_MAP.get(tdata.get('transaction_unit_type', 'cash'), '26')

        t_from = etree.SubElement(tx_el, 't_from_my_client')
        etree.SubElement(t_from, 'from_funds_code').text = funds_code
        ffc = etree.SubElement(t_from, 'from_foreign_currency')
        etree.SubElement(ffc, 'foreign_currency_code').text = tdata.get('currency_code', currency_code_local)
        etree.SubElement(ffc, 'foreign_amount').text = f"{tdata.get('currency_amount', 0):.2f}"
        _build_account(t_from, tdata.get('account', {}), currency_code_local, date_str, 'from_account')
        etree.SubElement(t_from, 'from_country').text = tdata.get('account', {}).get('country_code', 'CH')

        t_to = etree.SubElement(tx_el, 't_to_my_client')
        etree.SubElement(t_to, 'to_funds_code').text = funds_code
        tfc = etree.SubElement(t_to, 'to_foreign_currency')
        etree.SubElement(tfc, 'foreign_currency_code').text = tdata.get('currency_code', currency_code_local)
        etree.SubElement(tfc, 'foreign_amount').text = f"{tdata.get('currency_amount', 0):.2f}"
        to_person = etree.SubElement(t_to, 'to_person')
        addr = tdata.get('account', {}).get('address', {'address': 'Unknown', 'city': 'Unknown', 'country_code': 'CH', 'state': 'ZH'})
        _build_person(to_person, tdata.get('transaction_beneficiary', 'Unknown'), 'Unknown', addr)
        etree.SubElement(t_to, 'to_country').text = tdata.get('transaction_beneficiary_country_code', 'CH')

        comments = etree.SubElement(tx_el, 'comments')
        comments.text = f"local_label={tdata.get('local_label',0)};global_label={tdata.get('global_label',0)}"

    indicators = etree.SubElement(report, 'report_indicators')
    etree.SubElement(indicators, 'indicator').text = '1131V'
    etree.SubElement(indicators, 'indicator').text = '2003G'
    etree.SubElement(indicators, 'indicator').text = '0024M'

    additional_info = etree.SubElement(report, 'additional_information')
    info = etree.SubElement(additional_info, 'additional_info')
    etree.SubElement(info, 'info_type').text = 'BRNR'
    etree.SubElement(info, 'info_numeric').text = '1'

    return report


def validate_report(report):
    schema = xmlschema.XMLSchema11(SCHEMA_PATH)
    schema.validate(etree.ElementTree(report))


def verify_content(original_txs, report):
    xml_txs = report.findall('transaction')
    if len(xml_txs) != len(original_txs):
        raise ValueError('Mismatch in number of transactions')
    for xml_tx, orig_tx in zip(xml_txs, original_txs):
        if xml_tx.findtext('transactionnumber') != orig_tx['Transaction']['transaction_id']:
            raise ValueError('Transaction id mismatch')


def upload_report(xml_bytes, destination):
    if gs_utils.storage_client is None:
        return
    try:
        bucket = gs_utils.storage_client.bucket(gs_utils.BUCKET_NAME)
        blob = bucket.blob(destination)
        blob.upload_from_string(xml_bytes, content_type='application/xml')
    except Exception:
        pass


def group_by_party(sar_transactions, all_transactions):
    index = defaultdict(list)
    for tx in all_transactions:
        tdata = tx['Transaction']
        originator = tdata.get('transaction_originator')
        day = datetime.utcfromtimestamp(tdata['timestamp'] / 1000).strftime('%Y-%m-%d')
        index[(originator, day)].append(tx)
    grouped = {}
    for tx in sar_transactions:
        tdata = tx['Transaction']
        originator = tdata.get('transaction_originator')
        day = datetime.utcfromtimestamp(tdata['timestamp'] / 1000).strftime('%Y-%m-%d')
        grouped[(originator, day)] = index[(originator, day)]
    return grouped


def generate_parties(num_parties, banks, multi_bank_prob, multi_bank_distribution):
    fake.unique.clear()
    parties = []
    accounts = {b: {} for b in range(1, banks + 1)}
    multi_bank_count = 0
    for i in range(num_parties):
        pid = f'P{i+1}'
        first, last = fake.first_name(), fake.last_name()
        address = {
            'address': fake.street_address(),
            'city': fake.city(),
            'country_code': 'CH',
            'state': 'ZH',
        }
        party_info = {'id': pid, 'first_name': first, 'last_name': last, 'address': address}
        parties.append(party_info)
        if random.random() < multi_bank_prob:
            multi_bank_count += 1
            n_banks = random.randint(2, min(multi_bank_distribution, banks))
            bank_ids = random.sample(range(1, banks + 1), n_banks)
        else:
            bank_ids = [random.randint(1, banks)]
        for b in bank_ids:
            acc = {
                'bank_name': f'Bank_{b}',
                'account_id': fake.unique.bban(),
                'bic': f'BIC{b}{i+1}',
                'iban': f"CH{fake.unique.random_number(digits=19)}",
                'account_type': random.choice(['current', 'business']),
                'first_name': first,
                'last_name': last,
                'address': address,
                'balance_after': 0.0,
                'country_code': 'CH',
            }
            accounts[b][pid] = acc
    return parties, accounts, multi_bank_count


def generate_transactions_for_bank(bank_id, accounts, num_transactions, days_back, scenario_prob, bank_knows,
                                   std_multiplier, max_splits):
    transactions = []
    stats = {
        'scenario': 0,
        'non_scenario': 0,
        'spacing': {'uniform': 0, 'scattered': 0},
        'distribution': {'uniform': 0, 'skewed': 0},
        'labels': {'local1_global1': 0, 'local0_global1': 0, 'local0_global0': 0},
    }
    now = datetime.utcnow()
    base_mean = 1000
    base_std = 200
    threshold = base_mean + std_multiplier * base_std
    tx_id = 1
    while len(transactions) < num_transactions:
        party_id = random.choice(list(accounts.keys()))
        account = accounts[party_id]
        if random.random() < scenario_prob:
            total_amount = threshold * random.uniform(1.0, 2.0)
            splits = random.randint(1, max_splits)
            distribution = random.choice(['uniform', 'skewed'])
            spacing = random.choice(['uniform', 'scattered'])
            amounts = []
            if distribution == 'uniform':
                amounts = [total_amount / splits] * splits
            else:
                big = total_amount * 0.8
                rest = (total_amount - big) / (splits - 1 if splits > 1 else 1)
                amounts = [big] + [rest] * (splits - 1)
                random.shuffle(amounts)
            base_time = now - timedelta(days=random.randint(0, days_back))
            for idx in range(splits):
                ts = base_time if spacing == 'uniform' else base_time + timedelta(minutes=random.randint(1, 120) * idx)
                tdict = {
                    'Transaction': {
                        'transaction_id': f'B{bank_id}T{tx_id}',
                        'transaction_originator': party_id,
                        'transaction_type': 'deposit',
                        'transaction_unit_type': 'cash',
                        'currency_amount': round(amounts[idx], 2),
                        'currency_code': 'CHF',
                        'timestamp': int(ts.timestamp() * 1000),
                        'account': account,
                        'transaction_beneficiary': account['first_name'],
                        'transaction_beneficiary_country_code': 'CH',
                        'local_label': 1 if bank_knows else 0,
                        'global_label': 1,
                    }
                }
                transactions.append(tdict)
                stats['scenario'] += 1
                stats['spacing'][spacing] += 1
                stats['distribution'][distribution] += 1
                if bank_knows:
                    stats['labels']['local1_global1'] += 1
                else:
                    stats['labels']['local0_global1'] += 1
                tx_id += 1
                if len(transactions) >= num_transactions:
                    break
        else:
            ts = now - timedelta(days=random.randint(0, days_back))
            amount = max(1, random.gauss(base_mean, base_std))
            tdict = {
                'Transaction': {
                    'transaction_id': f'B{bank_id}T{tx_id}',
                    'transaction_originator': party_id,
                    'transaction_type': 'deposit',
                    'transaction_unit_type': 'cash',
                    'currency_amount': round(amount, 2),
                    'currency_code': 'CHF',
                    'timestamp': int(ts.timestamp() * 1000),
                    'account': account,
                    'transaction_beneficiary': account['first_name'],
                    'transaction_beneficiary_country_code': 'CH',
                    'local_label': 0,
                    'global_label': 0,
                }
            }
            transactions.append(tdict)
            stats['non_scenario'] += 1
            stats['labels']['local0_global0'] += 1
            tx_id += 1
    sums = defaultdict(float)
    for tx in transactions:
        acc = tx['Transaction']['account']
        sums[acc['account_id']] += tx['Transaction']['currency_amount']
    for acc in accounts.values():
        acc['balance_after'] = round(sums.get(acc['account_id'], 0.0), 2)
    return transactions, stats


def generate_reports(args):
    parties, all_accounts, multi_bank_count = generate_parties(
        args.parties, args.banks, args.multi_bank_prob, args.multi_bank_distribution
    )
    global_stats = {
        'scenario': 0,
        'non_scenario': 0,
        'spacing': {'uniform': 0, 'scattered': 0},
        'distribution': {'uniform': 0, 'skewed': 0},
        'labels': {'local1_global1': 0, 'local0_global1': 0, 'local0_global0': 0},
    }
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    folder = timestamp
    for bank_id in range(1, args.banks + 1):
        accounts = all_accounts[bank_id]
        if not accounts:
            continue
        scenario_prob = args.scenario_probability.get(str(bank_id), args.default_scenario_prob)
        bank_knows = args.bank_knowledge.get(str(bank_id), True)
        txs, bank_stats = generate_transactions_for_bank(
            bank_id,
            accounts,
            args.transactions,
            args.days,
            scenario_prob,
            bank_knows,
            args.std_multiplier,
            args.max_splits,
        )
        for key in ['scenario', 'non_scenario']:
            global_stats[key] += bank_stats[key]
        for key in ['uniform', 'scattered']:
            global_stats['spacing'][key] += bank_stats['spacing'][key]
        for key in ['uniform', 'skewed']:
            global_stats['distribution'][key] += bank_stats['distribution'][key]
        for key in global_stats['labels']:
            global_stats['labels'][key] += bank_stats['labels'][key]
        sar_transactions = [t for t in txs if t['Transaction']['local_label'] == 1]
        grouped = group_by_party(sar_transactions, txs)
        for (originator, day), group in grouped.items():
            for i in range(0, len(group), 1000):
                chunk = group[i:i + 1000]
                report = build_report(bank_id, 'LargeCashDeposit', originator, day, chunk, 'CHF')
                validate_report(report)
                verify_content(chunk, report)
                xml_bytes = etree.tostring(report, pretty_print=True, encoding='UTF-8', xml_declaration=True)
                filename = f'Bank_{bank_id}_LargeCashDeposit_{originator}_{day}_{timestamp}_{i//1000 + 1}.xml'
                path = f'{folder}/{filename}'
                upload_report(xml_bytes, path)
    print('--- Generation Statistics ---')
    print(f"Scenario transactions: {global_stats['scenario']}")
    print(f"Non-scenario transactions: {global_stats['non_scenario']}")
    print(f"Multi-bank parties: {multi_bank_count}")
    print(f"Spacing: {global_stats['spacing']}")
    print(f"Amount distribution: {global_stats['distribution']}")
    print(f"Labels: {global_stats['labels']}")


def main():
    parser = argparse.ArgumentParser(description='Generate synthetic transactions and goAML reports.')
    parser.add_argument('--banks', type=int, default=2)
    parser.add_argument('--transactions', type=int, default=1000)
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--parties', type=int, default=100)
    parser.add_argument('--multi_bank_prob', type=float, default=0.2)
    parser.add_argument('--multi_bank_distribution', type=int, default=2)
    parser.add_argument('--std_multiplier', type=float, default=2.0)
    parser.add_argument('--max_splits', type=int, default=3)
    parser.add_argument('--scenario_probability', type=str, default='{"1":0.2,"2":0.1}')
    parser.add_argument('--bank_knowledge', type=str, default='{"1":true,"2":false}')
    args = parser.parse_args()

    args.scenario_probability = json.loads(args.scenario_probability)
    args.bank_knowledge = json.loads(args.bank_knowledge)
    args.default_scenario_prob = 0.1

    generate_reports(args)


if __name__ == '__main__':
    import json
    main()
