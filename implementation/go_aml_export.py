import json
import os
from collections import defaultdict
from datetime import datetime
import logging

from lxml import etree
import xmlschema

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


def group_by_party(transactions):
    """Group transactions by (party_id, as_of_date)."""
    grouped = defaultdict(list)
    for tx in transactions:
        account = tx['Transaction'].get('account', {})
        for party in account.get('parties', []):
            key = (party['party_id'], party['as_of_date'])
            grouped[key].append(tx)
    return grouped


TYPE_MAP = {
    'CASH': 'CASHT',
    'SWIFT': 'B2BWT',
    '202': 'B2BWT',
    'SEPA': 'B2BWT',
}


def build_report(party_id, as_of_date, transactions):
    """Build the goAML XML report for a party and its transactions."""
    now_iso = datetime.utcnow().isoformat()
    report = etree.Element('report')
    etree.SubElement(report, 'rentity_id').text = '1'
    etree.SubElement(report, 'submission_code').text = 'E'
    etree.SubElement(report, 'report_code').text = 'SAR'
    etree.SubElement(report, 'entity_reference').text = f'{party_id}-{as_of_date}'
    etree.SubElement(report, 'report_date').text = now_iso
    etree.SubElement(report, 'currency_code_local').text = 'CHF'

    location = etree.SubElement(report, 'location')
    etree.SubElement(location, 'address_type').text = '1'
    etree.SubElement(location, 'address').text = 'Unknown'
    etree.SubElement(location, 'city').text = 'Unknown'
    etree.SubElement(location, 'zip').text = '0000'
    etree.SubElement(location, 'country_code').text = 'CH'
    etree.SubElement(location, 'state').text = 'ZH'

    etree.SubElement(report, 'reason').text = f'Suspicious activity for {party_id}'
    etree.SubElement(report, 'action').text = 'Transaction reported to authorities'

    for tx in transactions:
        tdata = tx['Transaction']
        tx_el = etree.SubElement(report, 'transaction')
        etree.SubElement(tx_el, 'transactionnumber').text = tdata['transaction_id']
        etree.SubElement(tx_el, 'transaction_description').text = (
            f'Transaction amount {tdata.get("currency_amount", 0)}'
        )
        dt_iso = datetime.utcfromtimestamp(tdata['timestamp'] / 1000).isoformat()
        etree.SubElement(tx_el, 'date_transaction').text = dt_iso
        etree.SubElement(tx_el, 'value_date').text = dt_iso
        tx_code = TYPE_MAP.get(tdata.get('transaction_type', '').upper(), 'B2BWT')
        etree.SubElement(tx_el, 'transaction_type_code').text = tx_code
        etree.SubElement(tx_el, 'amount_local').text = '0'
        involved = etree.SubElement(tx_el, 'involved_parties')
        party_el = etree.SubElement(involved, 'party')
        etree.SubElement(party_el, 'role').text = '1'
        person = etree.SubElement(party_el, 'person')
        etree.SubElement(person, 'first_name').text = 'Unknown'
        etree.SubElement(person, 'last_name').text = party_id
        etree.SubElement(party_el, 'comments').text = 'Acted as intermediary'

    report_indicators = etree.SubElement(report, 'report_indicators')
    etree.SubElement(report_indicators, 'indicator').text = '0024M'
    etree.SubElement(report_indicators, 'indicator').text = '1207V'
    etree.SubElement(report_indicators, 'indicator').text = '2103G'

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


def export_to_goaml(json_path):
    """Convert transaction data to goAML XML and upload to GCS."""
    transactions = load_transactions(json_path)
    sar_transactions = filter_sar_transactions(transactions)
    grouped = group_by_party(sar_transactions)

    bank_id = os.path.splitext(os.path.basename(json_path))[0]
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    folder = f'{timestamp}'

    for (party_id, as_of), txs in grouped.items():
        report = build_report(party_id, as_of, txs)
        validate_report(report)
        verify_content(txs, report)
        xml_bytes = etree.tostring(report, pretty_print=True, encoding='UTF-8', xml_declaration=True)
        filename = f'{bank_id}_{party_id}_{as_of}_{timestamp}.xml'
        gcs_path = f'{folder}/{filename}'
        upload_report(xml_bytes, gcs_path)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Export transactions to goAML XML format.')
    parser.add_argument('--input', default='example/Bank_1_transactions.json', help='Path to the transaction JSON file.')
    args = parser.parse_args()

    export_to_goaml(args.input)
