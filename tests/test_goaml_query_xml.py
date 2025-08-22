from lxml import etree
from tools.goaml_query import (
    unique_parties,
    related_parties,
    party_transactions,
    labelled_transactions,
)

SAMPLE_XML = '''
<report>
  <transaction>
    <t_from_my_client>
      <from_account>
        <institution_name>BankA</institution_name>
        <iban>IBAN1</iban>
        <related_persons>
          <account_related_person>
            <t_person>
              <first_name>Alice</first_name>
              <last_name>Sender</last_name>
              <birthdate>1970-01-01T00:00:00</birthdate>
              <addresses>
                <address>
                  <address>Street1</address>
                  <city>City1</city>
                  <country_code>CH</country_code>
                </address>
              </addresses>
            </t_person>
          </account_related_person>
        </related_persons>
      </from_account>
    </t_from_my_client>
    <t_to_my_client>
      <to_person>
        <first_name>Bob</first_name>
        <last_name>Receiver</last_name>
        <birthdate>1980-02-02T00:00:00</birthdate>
        <addresses>
          <address>
            <address>Street2</address>
            <city>City2</city>
            <country_code>CH</country_code>
          </address>
        </addresses>
      </to_person>
      <to_account>
        <institution_name>BankB</institution_name>
        <iban>IBAN2</iban>
      </to_account>
    </t_to_my_client>
    <amount_local>100.0</amount_local>
    <date_transaction>2023-01-01T00:00:00</date_transaction>
    <comments>local_label=1;global_label=1</comments>
  </transaction>
</report>
'''

def _transactions():
    root = etree.fromstring(SAMPLE_XML)
    return root.findall('transaction')

def test_unique_parties_sender_receiver():
    txs = _transactions()
    senders = unique_parties(txs, 'sending')
    receivers = unique_parties(txs, 'receiving')
    assert {p.name for p in senders} == {'Alice Sender'}
    assert {p.name for p in receivers} == {'Bob Receiver'}

def test_related_and_transactions():
    txs = _transactions()
    recs = related_parties(txs, 'Alice Sender', 'sending')
    assert [p.name for p in recs] == ['Bob Receiver']
    # Incoming for Bob
    records = party_transactions(
        txs,
        'Bob',
        'Receiver',
        '1980-02-02T00:00:00',
        start_balance=10.0,
    )
    assert len(records) == 1
    assert records[0].counterparty == 'Alice Sender'
    assert records[0].direction == 'in'
    assert records[0].amount == 100.0
    assert records[0].balance_after == 110.0
    # Outgoing for Alice
    records = party_transactions(
        txs,
        'Alice',
        'Sender',
        '1970-01-01T00:00:00',
        start_balance=10.0,
    )
    assert len(records) == 1
    assert records[0].counterparty == 'Bob Receiver'
    assert records[0].direction == 'out'
    assert records[0].amount == 100.0
    assert records[0].balance_after == -90.0


NESTED_XML = '''
<report>
  <transaction>
    <t_from_my_client>
      <from_account>
        <related_persons>
          <account_related_person>
            <t_person><first_name>Sender</first_name></t_person>
          </account_related_person>
        </related_persons>
      </from_account>
    </t_from_my_client>
    <t_to_my_client>
      <to_person>
        <t_person>
          <first_name>Jessica</first_name>
          <last_name>Hale</last_name>
          <birthdate>1948-11-07T00:00:00</birthdate>
        </t_person>
      </to_person>
    </t_to_my_client>
    <amount_local>50</amount_local>
    <date_transaction>2024-01-01T00:00:00</date_transaction>
  </transaction>
</report>
'''


def test_party_transactions_nested_person():
    root = etree.fromstring(NESTED_XML)
    txs = root.findall('transaction')
    records = party_transactions(txs, 'Jessica', 'Hale', '1948-11-07T00:00:00')
    assert len(records) == 1
    assert records[0].counterparty == 'Sender'


LABEL_XML = '''
<report>
  <transaction>
    <t_from_my_client><from_account><institution_name>BankA</institution_name><related_persons><account_related_person><t_person><first_name>S1</first_name></t_person></account_related_person></related_persons></from_account></t_from_my_client>
    <t_to_my_client><to_person><first_name>R1</first_name></to_person><to_account><institution_name>BankB</institution_name></to_account></t_to_my_client>
    <amount_local>1</amount_local>
    <date_transaction>2023-01-01T00:00:00</date_transaction>
    <comments>local_label=1;global_label=0</comments>
  </transaction>
  <transaction>
    <t_from_my_client><from_account><institution_name>BankA</institution_name><related_persons><account_related_person><t_person><first_name>S2</first_name></t_person></account_related_person></related_persons></from_account></t_from_my_client>
    <t_to_my_client><to_person><first_name>R2</first_name></to_person><to_account><institution_name>BankB</institution_name></to_account></t_to_my_client>
    <amount_local>2</amount_local>
    <date_transaction>2023-01-02T00:00:00</date_transaction>
    <comments>local_label=0;global_label=1</comments>
  </transaction>
  <transaction>
    <t_from_my_client><from_account><institution_name>BankA</institution_name><related_persons><account_related_person><t_person><first_name>S3</first_name></t_person></account_related_person></related_persons></from_account></t_from_my_client>
    <t_to_my_client><to_person><first_name>R3</first_name></to_person><to_account><institution_name>BankB</institution_name></to_account></t_to_my_client>
    <amount_local>3</amount_local>
    <date_transaction>2023-01-03T00:00:00</date_transaction>
    <comments>local_label=1;global_label=1</comments>
  </transaction>
</report>
'''


def test_labelled_transactions():
    root = etree.fromstring(LABEL_XML)
    txs = root.findall('transaction')
    assert len(labelled_transactions(txs, 'local')) == 2
    assert len(labelled_transactions(txs, 'global')) == 2
    assert len(labelled_transactions(txs, 'both')) == 1
