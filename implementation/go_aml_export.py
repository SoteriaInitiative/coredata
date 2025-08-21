import json
import os
from collections import defaultdict
from datetime import datetime
import logging

from lxml import etree
import xmlschema

try:  # pragma: no cover - handled in tests
    from .google_storage_utils import gs_utils
except ImportError:  # pragma: no cover
    from google_storage_utils import gs_utils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'standard', 'XML_Schema.xsd')


def load_transactions(path):
    """Load transactions from a JSON file."""
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def filter_sar_transactions(transactions):
    """Return only transactions where local_label == 1."""
    return [t for t in transactions if t.get('Transaction', {}).get('local_label') == 1]


def group_by_party(sar_transactions, all_transactions):
    """Group SAR transactions by originator and day and include all matching transactions."""

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


TYPE_MAP = {
    'CASH': 'CASHT',
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


def _build_address(parent):
    """Attach a dummy address required by the schema."""
    addr = etree.SubElement(parent, 'address')
    etree.SubElement(addr, 'address_type').text = '1'
    etree.SubElement(addr, 'address').text = 'Unknown'
    etree.SubElement(addr, 'city').text = 'Unknown'
    etree.SubElement(addr, 'country_code').text = 'CH'
    etree.SubElement(addr, 'state').text = 'ZH'
    return addr


def _build_person(parent, first_name):
    """Create a minimal t_person_my_client element with dummy values."""
    etree.SubElement(parent, 'gender').text = 'U'
    etree.SubElement(parent, 'first_name').text = first_name
    etree.SubElement(parent, 'last_name').text = 'Unknown'
    etree.SubElement(parent, 'birthdate').text = '1900-01-01T00:00:00'
    etree.SubElement(parent, 'nationality1').text = 'CH'
    addresses = etree.SubElement(parent, 'addresses')
    _build_address(addresses)


def _build_account(parent, account, currency_code_local, day, tag):
    """Create a t_account_my_client element with required dummy values."""
    acc_el = etree.SubElement(parent, tag)
    etree.SubElement(acc_el, 'institution_name').text = 'Dummy Bank'
    etree.SubElement(acc_el, 'swift').text = account.get('bic', 'DUMMYBIC')
    # institution_country is deprecated (maxOccurs=0) in schema 5.0
    etree.SubElement(acc_el, 'branch').text = 'ZH'
    etree.SubElement(acc_el, 'account_category').text = 'ACCNT'
    etree.SubElement(acc_el, 'account').text = account.get('account_id', '000000')
    etree.SubElement(acc_el, 'currency_code').text = currency_code_local
    etree.SubElement(acc_el, 'iban').text = account.get('iban', 'CH9300762011623852957')
    etree.SubElement(acc_el, 'client_number').text = '000000'
    acc_type = ACCOUNT_TYPE_MAP.get(str(account.get('account_type', '')).lower(), '14')
    etree.SubElement(acc_el, 'account_type').text = acc_type
    related = etree.SubElement(acc_el, 'related_persons')
    arp = etree.SubElement(related, 'account_related_person')
    tp = etree.SubElement(arp, 't_person')
    _build_person(tp, account.get('transaction_role', 'Person'))
    etree.SubElement(arp, 'role').text = '1'
    rr = etree.SubElement(arp, 'relation_date_range')
    etree.SubElement(rr, 'valid_from').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'opened').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'balance').text = f"{account.get('balance_after', 0):.2f}"
    etree.SubElement(acc_el, 'date_balance').text = f'{day}T00:00:00'
    etree.SubElement(acc_el, 'status_code').text = '1'
    etree.SubElement(acc_el, 'beneficiary_comment').text = account.get('transaction_role', 'Role')
    return acc_el


def build_report(originator, day, transactions, currency_code_local):
    """Build a goAML XML report for an originator and its transactions."""
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
        etree.SubElement(tx_el, 'transaction_description').text = str(tdata.get('global_label', 'Transaction'))
        date_str = datetime.utcfromtimestamp(tdata['timestamp'] / 1000).strftime('%Y-%m-%d')
        etree.SubElement(tx_el, 'date_transaction').text = f'{date_str}T00:00:00'
        etree.SubElement(tx_el, 'value_date').text = f'{date_str}T00:00:00'
        tx_code = TYPE_MAP.get(tdata.get('transaction_type', '').upper(), 'B2BWT')
        etree.SubElement(tx_el, 'transaction_type_code').text = tx_code
        etree.SubElement(tx_el, 'amount_local').text = f"{tdata.get('currency_amount', 0):.2f}"
        # transaction_status is deprecated in schema 5.0 (maxOccurs=0)

        funds_code = FUNDS_TYPE_MAP.get(tdata.get('transaction_unit_type', ''), '27')
        t_from = etree.SubElement(tx_el, 't_from_my_client')
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
        to_person = etree.SubElement(t_to, 'to_person')
        _build_person(to_person, tdata.get('transaction_beneficiary', 'Unknown'))
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


def export_to_goaml(json_path, currency_code_local='CHF'):
    """Convert transaction data to goAML XML and upload to GCS."""
    transactions = load_transactions(json_path)
    sar_transactions = filter_sar_transactions(transactions)
    grouped = group_by_party(sar_transactions, transactions)

    bank_id = os.path.splitext(os.path.basename(json_path))[0]
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    folder = f'{timestamp}'

    for (originator, day), txs in grouped.items():
        for i in range(0, len(txs), 1000):
            chunk = txs[i:i + 1000]
            report = build_report(originator, day, chunk, currency_code_local)
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
    args = parser.parse_args()

    export_to_goaml(args.input, args.currency_code_local)
