import argparse
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta

from faker import Faker
from faker.providers import BaseProvider
from lxml import etree
import xmlschema

try:
    from .google_storage_utils import gs_utils
except ImportError:  # pragma: no cover
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


class LeiProvider(BaseProvider):
    def lei(self):
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(self.random_choices(chars, length=20))


fake.add_provider(LeiProvider)

LEGAL_FORMS = ["AG", "GmbH", "LLC", "S.A.", "KG"]
LEGAL_FORM_CODES = {
    # Mapping aligned with goAML legal_form_type enumeration
    # 8: Limited company, 9: LLC, 12: Private limited partnership
    "AG": "8",
    "GmbH": "9",
    "LLC": "9",
    "S.A.": "8",
    "KG": "12",
}


def _build_address(parent, address):
    addr = etree.SubElement(parent, 'address')
    etree.SubElement(addr, 'address_type').text = '1'
    etree.SubElement(addr, 'address').text = address['address']
    etree.SubElement(addr, 'city').text = address['city']
    etree.SubElement(addr, 'country_code').text = address['country_code']
    etree.SubElement(addr, 'state').text = address['state']
    return addr


def _build_person(parent, first_name, last_name, address, birthdate):
    etree.SubElement(parent, 'gender').text = 'U'
    etree.SubElement(parent, 'first_name').text = first_name
    etree.SubElement(parent, 'last_name').text = last_name
    etree.SubElement(parent, 'birthdate').text = birthdate
    etree.SubElement(parent, 'nationality1').text = 'CH'
    addresses = etree.SubElement(parent, 'addresses')
    _build_address(addresses, address)


def _build_entity(parent, name, legal_form, address):
    etree.SubElement(parent, 'name').text = name
    etree.SubElement(parent, 'commercial_name').text = name
    etree.SubElement(parent, 'incorporation_legal_form').text = LEGAL_FORM_CODES.get(legal_form, '1')
    etree.SubElement(parent, 'incorporation_number').text = fake.lei()
    addresses = etree.SubElement(parent, 'addresses')
    _build_address(addresses, address)
    etree.SubElement(parent, 'incorporation_country_code').text = address.get('country_code', 'CH')
    etree.SubElement(parent, 'tax_reg_number').text = 'Yes'


def _build_account(parent, account, currency_code_local, day, tag):
    acc_el = etree.SubElement(parent, tag)
    etree.SubElement(acc_el, 'institution_name').text = account.get('bank_name', 'Dummy Bank')
    etree.SubElement(acc_el, 'swift').text = account.get('bic', 'DUMMYBIC')
    etree.SubElement(acc_el, 'branch').text = 'ZH'
    etree.SubElement(acc_el, 'account_category').text = 'ACCNT'
    etree.SubElement(acc_el, 'account').text = account.get('account_id', '000000')
    etree.SubElement(acc_el, 'currency_code').text = currency_code_local
    etree.SubElement(acc_el, 'iban').text = account.get('iban', 'CH9300762011623852957')
    client_num = account.get('client_number') or f"{fake.random_number(digits=6, fix_len=True)}"
    etree.SubElement(acc_el, 'client_number').text = str(client_num)
    acc_type = ACCOUNT_TYPE_MAP.get(account.get('account_type', 'current'), '1')
    etree.SubElement(acc_el, 'account_type').text = acc_type
    if account.get('party_type') == 'entity':
        related_entities = etree.SubElement(acc_el, 'related_entities')
        are = etree.SubElement(related_entities, 'account_related_entity')
        etree.SubElement(are, 'account_entity_relation').text = 'ACCCO'
        ent = etree.SubElement(are, 'entity')
        addr = account.get('address', {'address': 'Unknown', 'city': 'Unknown', 'country_code': 'CH', 'state': 'ZH'})
        _build_entity(ent, account.get('name', 'Unknown'), account.get('legal_form', 'AG'), addr)
        rr = etree.SubElement(are, 'relation_date_range')
        etree.SubElement(rr, 'valid_from').text = f'{day}T00:00:00'
        related_persons = etree.SubElement(acc_el, 'related_persons')
        arp = etree.SubElement(related_persons, 'account_related_person')
        tp = etree.SubElement(arp, 't_person')
        _build_person(
            tp,
            account.get('first_name', 'Unknown'),
            account.get('last_name', 'Unknown'),
            addr,
            account.get('birthdate', '1900-01-01T00:00:00'),
        )
        etree.SubElement(arp, 'role').text = '6'
        rr = etree.SubElement(arp, 'relation_date_range')
        etree.SubElement(rr, 'valid_from').text = f'{day}T00:00:00'
    else:
        related = etree.SubElement(acc_el, 'related_persons')
        arp = etree.SubElement(related, 'account_related_person')
        tp = etree.SubElement(arp, 't_person')
        addr = account.get('address', {'address': 'Unknown', 'city': 'Unknown', 'country_code': 'CH', 'state': 'ZH'})
        _build_person(
            tp,
            account.get('first_name', 'Unknown'),
            account.get('last_name', 'Unknown'),
            addr,
            account.get('birthdate', '1900-01-01T00:00:00'),
        )
        etree.SubElement(arp, 'role').text = '1'
        rr = etree.SubElement(arp, 'relation_date_range')
        etree.SubElement(rr, 'valid_from').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'opened').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'balance').text = f"{account.get('balance_after', 0):.2f}"
    etree.SubElement(acc_el, 'date_balance').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'status_code').text = '1'
    etree.SubElement(acc_el, 'beneficiary_comment').text = ' '
    return acc_el


def build_report(bank_id, originator, day, transactions, currency_code_local):
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

        loc_type = random.choice(['ATM', 'Counter'])
        loc_id = fake.bothify('????####')
        loc_addr = f"{fake.street_address()}, {fake.city()}"
        etree.SubElement(tx_el, 'transaction_location').text = f"{loc_type} {loc_id} {loc_addr}"
        etree.SubElement(tx_el, 'transaction_description').text = 'Cash Deposit'

        tx_datetime = datetime.utcfromtimestamp(tdata['timestamp'] / 1000)
        date_str = tx_datetime.strftime('%Y-%m-%d')
        ts_exact = tx_datetime.strftime('%Y-%m-%dT%H:%M:%S')
        etree.SubElement(tx_el, 'date_transaction').text = ts_exact
        etree.SubElement(tx_el, 'value_date').text = ts_exact
        tx_code = TYPE_MAP.get(tdata.get('transaction_type', 'deposit'), 'CASHT')
        etree.SubElement(tx_el, 'transaction_type_code').text = tx_code
        etree.SubElement(tx_el, 'amount_local').text = f"{tdata.get('currency_amount', 0):.2f}"

        t_from = etree.SubElement(tx_el, 't_from_my_client')
        etree.SubElement(t_from, 'from_funds_code').text = FUNDS_TYPE_MAP['cash']
        ffc = etree.SubElement(t_from, 'from_foreign_currency')
        etree.SubElement(ffc, 'foreign_currency_code').text = tdata.get('currency_code', currency_code_local)
        etree.SubElement(ffc, 'foreign_amount').text = f"{tdata.get('currency_amount', 0):.2f}"
        origin = tdata.get('originator', {})
        if origin.get('type') == 'entity':
            fe = etree.SubElement(t_from, 'from_entity')
            _build_entity(fe, origin.get('name', 'Unknown'), origin.get('legal_form', 'AG'), origin.get('address', {}))
        else:
            fp = etree.SubElement(t_from, 'from_person')
            _build_person(
                fp,
                origin.get('first_name', 'Unknown'),
                origin.get('last_name', 'Unknown'),
                origin.get('address', {'address': 'Unknown', 'city': 'Unknown', 'country_code': 'CH', 'state': 'ZH'}),
                origin.get('birthdate', '1900-01-01T00:00:00'),
            )
        etree.SubElement(t_from, 'from_country').text = origin.get('address', {}).get('country_code', 'CH')

        t_to = etree.SubElement(tx_el, 't_to_my_client')
        etree.SubElement(t_to, 'to_funds_code').text = FUNDS_TYPE_MAP['currency']
        tfc = etree.SubElement(t_to, 'to_foreign_currency')
        etree.SubElement(tfc, 'foreign_currency_code').text = tdata.get('currency_code', currency_code_local)
        etree.SubElement(tfc, 'foreign_amount').text = f"{tdata.get('currency_amount', 0):.2f}"
        _build_account(
            t_to,
            tdata.get('beneficiary_account', tdata.get('account', {})),
            currency_code_local,
            date_str,
            'to_account',
        )
        to_acc = tdata.get('beneficiary_account', tdata.get('account', {}))
        etree.SubElement(t_to, 'to_country').text = to_acc.get('country_code', 'CH')

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


def apply_global_labels(bank_transactions):
    scenario_presence = defaultdict(set)
    for bank_id, txs in bank_transactions.items():
        for tx in txs:
            if tx['Transaction'].get('scenario'):
                scenario_presence[tx['Transaction']['beneficiary_id']].add(bank_id)
    for bank_id, txs in bank_transactions.items():
        for tx in txs:
            if tx['Transaction'].get('scenario'):
                origin = tx['Transaction']['beneficiary_id']
                tx['Transaction']['global_label'] = 1 if len(scenario_presence[origin]) > 1 else 0


def group_by_party(transactions):
    grouped = defaultdict(list)
    for tx in transactions:
        tdata = tx['Transaction']
        originator = tdata.get('transaction_originator')
        day = datetime.utcfromtimestamp(tdata['timestamp'] / 1000).strftime('%Y-%m-%d')
        grouped[(originator, day)].append(tx)
    return grouped


def generate_parties(num_parties, banks, multi_bank_prob, multi_bank_distribution):
    fake.unique.clear()
    parties = {}
    receivers = {}
    accounts = {b: {} for b in range(1, banks + 1)}
    multi_bank_count = 0
    has_entity_party = False
    has_entity_receiver = False
    for i in range(num_parties):
        pid = f'P{i+1}'
        address = {
            'address': fake.street_address(),
            'city': fake.city(),
            'country_code': 'CH',
            'state': 'ZH',
        }

        # Decide party type; ensure at least one entity overall
        if not has_entity_party and i == num_parties - 1:
            party_type = 'entity'
        else:
            party_type = random.choice(['person', 'entity'])

        if party_type == 'person':
            first, last = fake.first_name(), fake.last_name()
            birthdate = fake.date_of_birth(minimum_age=18, maximum_age=90).strftime('%Y-%m-%dT00:00:00')
            party_info = {
                'id': pid,
                'type': 'person',
                'first_name': first,
                'last_name': last,
                'birthdate': birthdate,
                'address': address,
            }
        else:
            legal_form = random.choice(LEGAL_FORMS)
            name = f"{fake.company()} {legal_form}"
            party_info = {
                'id': pid,
                'type': 'entity',
                'name': name,
                'legal_form': legal_form,
                'address': address,
            }
            has_entity_party = True

        parties[pid] = party_info

        # Receiver generation; ensure at least one entity receiver overall
        if not has_entity_receiver and i == num_parties - 1:
            recv_type = 'entity'
        else:
            recv_type = random.choice(['person', 'entity'])

        if recv_type == 'person':
            recv_first = fake.first_name()
            while recv_first == party_info.get('first_name'):
                recv_first = fake.first_name()
            recv_last = fake.last_name()
            while recv_last == party_info.get('last_name'):
                recv_last = fake.last_name()
            recv_birth = fake.date_of_birth(minimum_age=18, maximum_age=90).strftime('%Y-%m-%dT00:00:00')
            while recv_birth == party_info.get('birthdate'):
                recv_birth = fake.date_of_birth(minimum_age=18, maximum_age=90).strftime('%Y-%m-%dT00:00:00')
            receivers[pid] = {
                'type': 'person',
                'first_name': recv_first,
                'last_name': recv_last,
                'birthdate': recv_birth,
                'address': address,
            }
        else:
            rform = random.choice(LEGAL_FORMS)
            rname = f"{fake.company()} {rform}"
            receivers[pid] = {
                'type': 'entity',
                'name': rname,
                'legal_form': rform,
                'address': address,
            }
            has_entity_receiver = True

        if random.random() < multi_bank_prob:
            multi_bank_count += 1
            n_banks = random.randint(2, min(multi_bank_distribution, banks))
            bank_ids = random.sample(range(1, banks + 1), n_banks)
        else:
            bank_ids = [random.randint(1, banks)]

        receivers[pid]['accounts'] = {}
        for b in bank_ids:
            acc = {
                'bank_name': f'Bank_{b}',
                'account_id': fake.unique.bban(),
                'bic': f'BICR{i+1}B{b}',
                'iban': f"CH{fake.unique.random_number(digits=19)}",
                'account_type': random.choice(['current', 'business']),
                'address': address,
                'initial_balance': round(random.uniform(0, 1000), 2),
                'balance_after': 0.0,
                'country_code': 'CH',
                'party_type': recv_type,
                'client_number': fake.random_number(digits=6, fix_len=True),
            }
            if recv_type == 'person':
                acc.update({
                    'first_name': receivers[pid]['first_name'],
                    'last_name': receivers[pid]['last_name'],
                    'birthdate': receivers[pid]['birthdate'],
                })
            else:
                acc.update({
                    'name': receivers[pid]['name'],
                    'legal_form': receivers[pid]['legal_form'],
                    'first_name': fake.first_name(),
                    'last_name': fake.last_name(),
                    'birthdate': fake.date_of_birth(minimum_age=18, maximum_age=90).strftime('%Y-%m-%dT00:00:00'),
                })
            receivers[pid]['accounts'][b] = acc
            accounts[b][pid] = acc
    return parties, receivers, accounts, multi_bank_count


def generate_transactions_for_bank(bank_id, accounts, receivers, parties, num_transactions, days_back, scenario_prob, bank_knows,
                                   std_multiplier, max_splits):
    transactions = []
    stats = {
        'scenario': 0,
        'non_scenario': 0,
        'spacing': {'uniform': 0, 'scattered': 0},
        'distribution': {'uniform': 0, 'skewed': 0},
    }
    now = datetime.utcnow()
    base_mean = 1000
    base_std = 200
    threshold = base_mean + std_multiplier * base_std
    tx_id = 1

    # Ensure each account receives at least one transaction
    for party_id, account in accounts.items():
        beneficiary = receivers[party_id]
        originator = parties[party_id]
        ts = now - timedelta(
            days=random.randint(0, days_back),
            seconds=random.randint(0, 86400 - 1),
        )
        amount = max(1, random.gauss(base_mean, base_std))
        recv_acc = beneficiary['accounts'][bank_id]
        balance = recv_acc.setdefault('current_balance', recv_acc['initial_balance']) + amount
        recv_acc['current_balance'] = balance
        acc_snapshot = recv_acc.copy()
        acc_snapshot['balance_after'] = round(balance, 2)
        acc_snapshot['last_ts'] = None
        recv_snapshot = acc_snapshot

        tdict = {
            'Transaction': {
                'transaction_id': f'B{bank_id}T{tx_id}',
                'transaction_originator': party_id,
                'beneficiary_id': party_id,
                'originator': originator,
                'transaction_type': 'deposit',
                'transaction_unit_type': 'cash',
                'currency_amount': round(amount, 2),
                'currency_code': 'CHF',
                'timestamp': int(ts.timestamp() * 1000),
                'account': acc_snapshot,
                'transaction_beneficiary': beneficiary.get('first_name', beneficiary.get('name', '')),
                'transaction_beneficiary_country_code': 'CH',
                'beneficiary': beneficiary,
                'beneficiary_account': recv_snapshot,
                'local_label': 0,
                'global_label': 0,
                'scenario': False,
            }
        }
        transactions.append(tdict)
        stats['non_scenario'] += 1
        tx_id += 1
        account['last_ts'] = ts
        beneficiary['accounts'][bank_id]['last_ts'] = ts

    while len(transactions) < num_transactions:
        party_id = random.choice(list(accounts.keys()))
        account = accounts[party_id]
        beneficiary = receivers[party_id]
        originator = parties[party_id]
        last_ts = account.get('last_ts')
        recv_last_ts = beneficiary['accounts'][bank_id].get('last_ts')
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
            base_time = now - timedelta(
                days=random.randint(0, days_back),
                seconds=random.randint(0, 86400 - 1),
            )
            for idx in range(splits):
                ts = base_time if spacing == 'uniform' else base_time + timedelta(
                    minutes=random.randint(1, 120) * idx
                )
                if last_ts and ts <= last_ts:
                    ts = last_ts + timedelta(seconds=1)
                if recv_last_ts and ts <= recv_last_ts:
                    ts = recv_last_ts + timedelta(seconds=1)
                last_ts = ts
                recv_last_ts = ts
                amount = round(amounts[idx], 2)
                local_label = 1 if bank_knows and amount >= threshold else 0

                recv_acc = beneficiary['accounts'][bank_id]
                balance = recv_acc.setdefault('current_balance', recv_acc['initial_balance']) + amount
                recv_acc['current_balance'] = balance
                acc_snapshot = recv_acc.copy()
                acc_snapshot['balance_after'] = round(balance, 2)
                acc_snapshot['last_ts'] = None
                recv_snapshot = acc_snapshot

                tdict = {
                    'Transaction': {
                        'transaction_id': f'B{bank_id}T{tx_id}',
                        'transaction_originator': party_id,
                        'beneficiary_id': party_id,
                        'originator': originator,
                        'transaction_type': 'deposit',
                        'transaction_unit_type': 'cash',
                        'currency_amount': amount,
                        'currency_code': 'CHF',
                        'timestamp': int(ts.timestamp() * 1000),
                        'account': acc_snapshot,
                        'transaction_beneficiary': beneficiary.get('first_name', beneficiary.get('name', '')),
                        'transaction_beneficiary_country_code': 'CH',
                        'beneficiary': beneficiary,
                        'beneficiary_account': recv_snapshot,
                        'local_label': local_label,
                        'global_label': 0,
                        'scenario': True,
                        'spacing': spacing,
                        'distribution': distribution,
                    }
                }
                transactions.append(tdict)
                stats['scenario'] += 1
                stats['spacing'][spacing] += 1
                stats['distribution'][distribution] += 1
                tx_id += 1
                if len(transactions) >= num_transactions:
                    break
            account['last_ts'] = last_ts
            beneficiary['accounts'][bank_id]['last_ts'] = recv_last_ts
        else:
            ts = now - timedelta(
                days=random.randint(0, days_back),
                seconds=random.randint(0, 86400 - 1),
            )
            if last_ts and ts <= last_ts:
                ts = last_ts + timedelta(seconds=1)
            if recv_last_ts and ts <= recv_last_ts:
                ts = recv_last_ts + timedelta(seconds=1)
            last_ts = ts
            recv_last_ts = ts
            amount = max(1, random.gauss(base_mean, base_std))

            recv_acc = beneficiary['accounts'][bank_id]
            balance = recv_acc.setdefault('current_balance', recv_acc['initial_balance']) + amount
            recv_acc['current_balance'] = balance
            acc_snapshot = recv_acc.copy()
            acc_snapshot['balance_after'] = round(balance, 2)
            acc_snapshot['last_ts'] = None
            recv_snapshot = acc_snapshot

            tdict = {
                'Transaction': {
                    'transaction_id': f'B{bank_id}T{tx_id}',
                    'transaction_originator': party_id,
                    'beneficiary_id': party_id,
                    'originator': originator,
                    'transaction_type': 'deposit',
                    'transaction_unit_type': 'cash',
                    'currency_amount': round(amount, 2),
                    'currency_code': 'CHF',
                    'timestamp': int(ts.timestamp() * 1000),
                    'account': acc_snapshot,
                    'transaction_beneficiary': beneficiary.get('first_name', beneficiary.get('name', '')),
                    'transaction_beneficiary_country_code': 'CH',
                    'beneficiary': beneficiary,
                    'beneficiary_account': recv_snapshot,
                    'local_label': 0,
                    'global_label': 0,
                    'scenario': False,
                }
            }
            transactions.append(tdict)
            stats['non_scenario'] += 1
            tx_id += 1
            account['last_ts'] = last_ts
            beneficiary['accounts'][bank_id]['last_ts'] = recv_last_ts
    for acc in accounts.values():
        acc['balance_after'] = round(acc.get('current_balance', acc['initial_balance']), 2)
    for recv in receivers.values():
        for r_acc in recv['accounts'].values():
            r_acc['balance_after'] = round(r_acc.get('current_balance', r_acc['initial_balance']), 2)
    return transactions, stats


def generate_reports(args):
    parties, receivers, all_accounts, multi_bank_count = generate_parties(
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
    bank_transactions = {}
    for bank_id in range(1, args.banks + 1):
        accounts = all_accounts[bank_id]
        if not accounts:
            continue
        scenario_prob = args.scenario_probability.get(str(bank_id), args.default_scenario_prob)
        bank_knows = args.bank_knowledge.get(str(bank_id), True)
        txs, bank_stats = generate_transactions_for_bank(
            bank_id,
            accounts,
            receivers,
            parties,
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
        bank_transactions[bank_id] = txs

    apply_global_labels(bank_transactions)

    for bank_id, txs in bank_transactions.items():
        grouped = group_by_party(txs)
        for (originator, day), group in grouped.items():
            for i in range(0, len(group), 1000):
                chunk = group[i:i + 1000]
                report = build_report(bank_id, originator, day, chunk, 'CHF')
                verify_content(chunk, report)
                xml_bytes = etree.tostring(report, pretty_print=True, encoding='UTF-8', xml_declaration=True)
                filename = f'Bank_{bank_id}_LargeCashDeposit_{originator}_{day}_{timestamp}_{i//1000 + 1}.xml'
                path = f'{folder}/{filename}'
                upload_report(xml_bytes, path)

        for tx in txs:
            local = tx['Transaction']['local_label']
            global_l = tx['Transaction']['global_label']
            if local == 1 and global_l == 1:
                global_stats['labels']['local1_global1'] += 1
            elif local == 0 and global_l == 1:
                global_stats['labels']['local0_global1'] += 1
            else:
                global_stats['labels']['local0_global0'] += 1

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
