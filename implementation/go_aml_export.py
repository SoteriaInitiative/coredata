import json
import os
import random
from collections import defaultdict
from datetime import datetime
import logging

from lxml import etree
import xmlschema
from faker import Faker
from . import generate_goaml

try:  # pragma: no cover - handled in tests
    from .google_storage_utils import gs_utils
except ImportError:  # pragma: no cover
    from google_storage_utils import gs_utils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

fake = Faker()

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'standard', 'XML_Schema.xsd')


def load_transactions(path):
    """Load transactions from a JSON file."""
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def update_account_balances(transactions):
    """Recalculate running balances for each account."""
    by_account = defaultdict(list)
    for tx in transactions:
        acc = tx.get('Transaction', {}).get('account')
        if acc:
            by_account[acc.get('account_id')].append(tx)

    for acc_id, txs in by_account.items():
        txs.sort(key=lambda t: t['Transaction']['timestamp'])
        initial = txs[0]['Transaction']['account'].get('balance_before', 0.0)
        running = initial
        for tx in txs:
            tdata = tx['Transaction']
            acc = tdata['account']
            acc['balance_before'] = round(running, 2)
            running += tdata.get('currency_amount', 0.0)
            acc['balance_after'] = round(running, 2)


def group_by_party(transactions):
    """Group all transactions by originator and UTC day."""

    index = defaultdict(list)
    for tx in transactions:
        tdata = tx['Transaction']
        originator = tdata.get('transaction_originator')
        day = datetime.utcfromtimestamp(tdata['timestamp'] / 1000).strftime('%Y-%m-%d')
        index[(originator, day)].append(tx)
    return index


TYPE_MAP = {
    'CASH': 'CASHT',
    'DEPOSIT': 'CASHT',
    'SWIFT': 'B2BWT',
    '202': 'B2BWT',
    'SEPA': 'B2BWT',
}

FUNDS_TYPE_MAP = {
    'currency': '27',
    'cash': '26',
    'crypto': '2',
    'securities': '20',
}

ACCOUNT_TYPE_MAP = {
    'investment': '14',
    'debit': '10',
    'business': '1',
}


def _build_address(parent, address=None):
    """Attach an address element."""
    addr = etree.SubElement(parent, 'address')
    etree.SubElement(addr, 'address_type').text = '1'
    address = address or {'address': 'Unknown', 'city': 'Unknown', 'country_code': 'CH', 'state': 'ZH'}
    etree.SubElement(addr, 'address').text = address['address']
    etree.SubElement(addr, 'city').text = address['city']
    etree.SubElement(addr, 'country_code').text = address['country_code']
    etree.SubElement(addr, 'state').text = address['state']
    return addr


def _build_person(parent, info):
    """Create a t_person or t_person_my_client element."""
    etree.SubElement(parent, 'gender').text = 'U'
    etree.SubElement(parent, 'first_name').text = info.get('first_name', 'Unknown')
    etree.SubElement(parent, 'last_name').text = info.get('last_name', 'Unknown')
    etree.SubElement(parent, 'birthdate').text = info.get('birthdate', '1900-01-01T00:00:00')
    etree.SubElement(parent, 'nationality1').text = info.get('nationality', 'CH')
    addresses = etree.SubElement(parent, 'addresses')
    _build_address(addresses, info.get('address'))


def _build_entity(parent, info):
    """Create a t_entity_my_client element."""
    name = info.get('name', 'Dummy Corp')
    etree.SubElement(parent, 'name').text = name
    etree.SubElement(parent, 'commercial_name').text = name
    form = info.get('legal_form', 'AG')
    form_code = generate_goaml.LEGAL_FORM_CODES.get(form, '1')
    etree.SubElement(parent, 'incorporation_legal_form').text = form_code
    addresses = etree.SubElement(parent, 'addresses')
    _build_address(addresses, info.get('address'))
    etree.SubElement(parent, 'incorporation_country_code').text = info.get('address', {}).get('country_code', 'CH')
    etree.SubElement(parent, 'tax_reg_number').text = 'Yes'


def _build_account(parent, account, currency_code_local, day, tag):
    """Create a t_account_my_client element with required values."""
    acc_el = etree.SubElement(parent, tag)
    etree.SubElement(acc_el, 'institution_name').text = account.get('bank_name', 'Dummy Bank')
    etree.SubElement(acc_el, 'swift').text = account.get('bic', 'DUMMYBIC')
    etree.SubElement(acc_el, 'branch').text = 'ZH'
    etree.SubElement(acc_el, 'account_category').text = 'ACCNT'
    etree.SubElement(acc_el, 'account').text = account.get('account_id', '000000')
    etree.SubElement(acc_el, 'currency_code').text = currency_code_local
    etree.SubElement(acc_el, 'iban').text = account.get('iban', 'CH9300762011623852957')
    etree.SubElement(acc_el, 'client_number').text = '000000'
    acc_type = ACCOUNT_TYPE_MAP.get(str(account.get('account_type', '')).lower(), '14')
    etree.SubElement(acc_el, 'account_type').text = acc_type
    if account.get('party_type') == 'entity':
        related = etree.SubElement(acc_el, 'related_entities')
        are = etree.SubElement(related, 'account_related_entity')
        etree.SubElement(are, 'account_entity_relation').text = 'ACCCO'
        entity = etree.SubElement(are, 'entity')
        _build_entity(entity, account)
        rr = etree.SubElement(are, 'relation_date_range')
        etree.SubElement(rr, 'valid_from').text = f'{day}T00:00:00'
        related_persons = etree.SubElement(acc_el, 'related_persons')
        arp = etree.SubElement(related_persons, 'account_related_person')
        tp = etree.SubElement(arp, 't_person')
        _build_person(tp, account)
        etree.SubElement(arp, 'role').text = '1'
        rr = etree.SubElement(arp, 'relation_date_range')
        etree.SubElement(rr, 'valid_from').text = f'{day}T00:00:00'
    else:
        related = etree.SubElement(acc_el, 'related_persons')
        arp = etree.SubElement(related, 'account_related_person')
        tp = etree.SubElement(arp, 't_person')
        _build_person(tp, account)
        etree.SubElement(arp, 'role').text = '1'
        rr = etree.SubElement(arp, 'relation_date_range')
        etree.SubElement(rr, 'valid_from').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'opened').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'balance').text = f"{account.get('balance_after', 0):.2f}"
    etree.SubElement(acc_el, 'date_balance').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'status_code').text = '1'
    etree.SubElement(acc_el, 'beneficiary_comment').text = account.get('transaction_role', 'Role')
    return acc_el


def build_report(originator, day, transactions, currency_code_local, same_person_prob=0.9):
    """Build a goAML XML report for an originator and its transactions.

    Parameters
    ----------
    originator : str
        Identifier for the transaction originator.
    day : str
        UTC day (YYYY-MM-DD) of the transactions being reported.
    transactions : list
        List of transaction dictionaries.
    currency_code_local : str
        Local currency code (e.g. CHF).
    same_person_prob : float, optional
        Probability that the depositor (from_person) is the same individual as
        the related person on the credited account. Defaults to 0.9.
    """
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
        tx_code = TYPE_MAP.get(tdata.get('transaction_type', '').upper(), 'B2BWT')
        etree.SubElement(tx_el, 'transaction_type_code').text = tx_code
        etree.SubElement(tx_el, 'amount_local').text = f"{tdata.get('currency_amount', 0):.2f}"
        # transaction_status is deprecated in schema 5.0 (maxOccurs=0)

        funds_code = FUNDS_TYPE_MAP.get(tdata.get('transaction_unit_type', ''), '27')
        t_from = etree.SubElement(tx_el, 't_from_my_client')
        if tx_code == 'CASHT' and funds_code == FUNDS_TYPE_MAP.get('cash'):
            etree.SubElement(t_from, 'from_funds_code').text = FUNDS_TYPE_MAP['cash']
            ffc = etree.SubElement(t_from, 'from_foreign_currency')
            etree.SubElement(ffc, 'foreign_currency_code').text = tdata.get('currency_code', currency_code_local)
            etree.SubElement(ffc, 'foreign_amount').text = f"{tdata.get('currency_amount', 0):.2f}"
            if tdata.get('exchange_rate'):
                etree.SubElement(ffc, 'foreign_exchange_rate').text = str(
                    tdata['exchange_rate'].get('exchange_rate', 1)
                )
            originator = tdata.get('originator', {})
            # ensure we have originator details
            if not originator:
                originator.update({
                    'first_name': fake.first_name(),
                    'last_name': fake.last_name(),
                    'birthdate': fake.date_of_birth(minimum_age=18, maximum_age=90).strftime('%Y-%m-%dT00:00:00'),
                    'address': {
                        'address': fake.street_address(),
                        'city': fake.city(),
                        'country_code': 'CH',
                        'state': 'ZH',
                    },
                })

            if originator.get('type') == 'entity':
                fe = etree.SubElement(t_from, 'from_entity')
                _build_entity(fe, originator)
            else:
                fp = etree.SubElement(t_from, 'from_person')
                _build_person(fp, originator)
            from_country = originator.get('address', {}).get('country_code', tdata.get('account', {}).get('country_code', 'CH'))
            if from_country == 'UK':
                from_country = 'GB'
            etree.SubElement(t_from, 'from_country').text = from_country

            t_to = etree.SubElement(tx_el, 't_to_my_client')
            etree.SubElement(t_to, 'to_funds_code').text = FUNDS_TYPE_MAP['currency']
            tfc = etree.SubElement(t_to, 'to_foreign_currency')
            etree.SubElement(tfc, 'foreign_currency_code').text = tdata.get('currency_code', currency_code_local)
            etree.SubElement(tfc, 'foreign_amount').text = f"{tdata.get('currency_amount', 0):.2f}"
            if tdata.get('exchange_rate'):
                etree.SubElement(tfc, 'foreign_exchange_rate').text = str(
                    tdata['exchange_rate'].get('exchange_rate', 1)
                )
            account_info = tdata.get('account', {}).copy()
            if random.random() < same_person_prob:
                account_info.update({
                    'first_name': originator.get('first_name', 'Unknown'),
                    'last_name': originator.get('last_name', 'Unknown'),
                    'birthdate': originator.get('birthdate', '1900-01-01T00:00:00'),
                    'address': originator.get('address'),
                })
            else:
                if not account_info.get('first_name'):
                    account_info.update({
                        'first_name': fake.first_name(),
                        'last_name': fake.last_name(),
                        'birthdate': fake.date_of_birth(minimum_age=18, maximum_age=90).strftime('%Y-%m-%dT00:00:00'),
                        'address': {
                            'address': fake.street_address(),
                            'city': fake.city(),
                            'country_code': 'CH',
                            'state': 'ZH',
                        },
                    })
            _build_account(t_to, account_info, currency_code_local, date_str, 'to_account')
            to_country = tdata.get('account', {}).get('country_code', 'CH')
            if to_country == 'UK':
                to_country = 'GB'
            etree.SubElement(t_to, 'to_country').text = to_country
        else:
            etree.SubElement(t_from, 'from_funds_code').text = funds_code
            ffc = etree.SubElement(t_from, 'from_foreign_currency')
            etree.SubElement(ffc, 'foreign_currency_code').text = tdata.get('currency_code', currency_code_local)
            etree.SubElement(ffc, 'foreign_amount').text = f"{tdata.get('currency_amount', 0):.2f}"
            if tdata.get('exchange_rate'):
                etree.SubElement(ffc, 'foreign_exchange_rate').text = str(
                    tdata['exchange_rate'].get('exchange_rate', 1)
                )
            _build_account(t_from, tdata.get('account', {}), currency_code_local, date_str, 'from_account')
            from_country = tdata.get('account', {}).get('country_code', 'CH')
            if from_country == 'UK':
                from_country = 'GB'
            etree.SubElement(t_from, 'from_country').text = from_country

            t_to = etree.SubElement(tx_el, 't_to_my_client')
            etree.SubElement(t_to, 'to_funds_code').text = funds_code
            tfc = etree.SubElement(t_to, 'to_foreign_currency')
            etree.SubElement(tfc, 'foreign_currency_code').text = tdata.get('currency_code', currency_code_local)
            etree.SubElement(tfc, 'foreign_amount').text = f"{tdata.get('currency_amount', 0):.2f}"
            if tdata.get('exchange_rate'):
                etree.SubElement(tfc, 'foreign_exchange_rate').text = str(
                    tdata['exchange_rate'].get('exchange_rate', 1)
                )
            beneficiary = tdata.get('beneficiary', {})
            if beneficiary.get('type') == 'entity':
                to_entity = etree.SubElement(t_to, 'to_entity')
                _build_entity(to_entity, beneficiary)
            else:
                to_person = etree.SubElement(t_to, 'to_person')
                _build_person(to_person, beneficiary)
            to_country = tdata.get('transaction_beneficiary_country_code', 'CH')
            if to_country == 'UK':
                to_country = 'GB'
            etree.SubElement(t_to, 'to_country').text = to_country

        comments = etree.SubElement(tx_el, 'comments')
        comments.text = (
            f"local_label={tdata.get('local_label',0)};"
            f"global_label={tdata.get('global_label',0)}"
        )

    report_indicators = etree.SubElement(report, 'report_indicators')
    etree.SubElement(report_indicators, 'indicator').text = '1131V'
    etree.SubElement(report_indicators, 'indicator').text = '2003G'
    etree.SubElement(report_indicators, 'indicator').text = '0024M'

    additional_info = etree.SubElement(report, 'additional_information')
    info = etree.SubElement(additional_info, 'additional_info')
    etree.SubElement(info, 'info_type').text = 'BRNR'
    etree.SubElement(info, 'info_numeric').text = '1'

    return report


def validate_report(report):
    """Validate the XML report against the goAML XSD."""
    schema = xmlschema.XMLSchema11(SCHEMA_PATH)
    schema.validate(etree.ElementTree(report))


def verify_content(original_txs, report):
    """Verify that the XML report contains the same transaction ids and amounts."""
    xml_txs = report.findall('transaction')
    if len(xml_txs) != len(original_txs):
        raise ValueError('Mismatch in number of transactions')
    for xml_tx, orig_tx in zip(xml_txs, original_txs):
        if xml_tx.findtext('transactionnumber') != orig_tx['Transaction']['transaction_id']:
            raise ValueError('Transaction id mismatch')


def upload_report(xml_bytes, destination):
    """Upload the XML bytes to Google Cloud Storage."""
    if gs_utils.storage_client is None:
        logger.error('Google Cloud Storage client not configured.')
        return
    try:
        bucket = gs_utils.storage_client.bucket(gs_utils.BUCKET_NAME)
        blob = bucket.blob(destination)
        blob.upload_from_string(xml_bytes, content_type='application/xml')
        logger.info('Uploaded report to %s', destination)
    except Exception as exc:
        logger.error('Failed to upload report %s: %s', destination, exc)


def export_to_goaml(json_path, currency_code_local='CHF', same_person_prob=0.9):
    """Convert transaction data to goAML XML and upload to GCS.

    Parameters
    ----------
    json_path : str
        Path to the transactions JSON file.
    currency_code_local : str, optional
        Local currency code to use for amounts.
    same_person_prob : float, optional
        Probability that deposits are made into the depositor's own account.
        Defaults to 0.9.
    """
    transactions = load_transactions(json_path)
    update_account_balances(transactions)
    grouped = group_by_party(transactions)

    bank_id = os.path.splitext(os.path.basename(json_path))[0]
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    folder = f'{timestamp}'

    for (originator, day), txs in grouped.items():
        for i in range(0, len(txs), 1000):
            chunk = txs[i:i + 1000]
            report = build_report(originator, day, chunk, currency_code_local, same_person_prob)
            validate_report(report)
            verify_content(chunk, report)
            xml_bytes = etree.tostring(report, pretty_print=True, encoding='UTF-8', xml_declaration=True)
            filename = f'{bank_id}_{originator}_{day}_{timestamp}_{i//1000 + 1}.xml'
            gcs_path = f'{folder}/{filename}'
            upload_report(xml_bytes, gcs_path)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Export transactions to goAML XML format.')
    parser.add_argument('--input', default='example/Bank_1_transactions.json', help='Path to the transaction JSON file.')
    parser.add_argument('--currency_code_local', default='CHF', help='Currency code used for local amounts.')
    parser.add_argument(
        '--same_person_prob',
        type=float,
        default=0.9,
        help='Probability that the depositor is also the related person on the credited account.'
    )
    args = parser.parse_args()

    export_to_goaml(args.input, args.currency_code_local, args.same_person_prob)
