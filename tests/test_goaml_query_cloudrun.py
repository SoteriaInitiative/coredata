from lxml import etree

import tools.goaml_query as gq


SAMPLE_XML = """
<report>
  <transaction>
    <t_from_my_client>
      <from_person>
        <first_name>Alice</first_name>
        <last_name>Sender</last_name>
        <birthdate>1970-01-01T00:00:00</birthdate>
        <addresses><address><address>Street1</address></address></addresses>
      </from_person>
      <from_account>
        <institution_name>BankA</institution_name>
        <iban>IBAN1</iban>
        <balance>900.0</balance>
      </from_account>
    </t_from_my_client>
    <t_to_my_client>
      <to_person>
        <first_name>Bob</first_name>
        <last_name>Receiver</last_name>
        <birthdate>1980-02-02T00:00:00</birthdate>
        <addresses><address><address>Street2</address></address></addresses>
      </to_person>
      <to_account>
        <institution_name>BankB</institution_name>
        <iban>IBAN2</iban>
        <balance>1100.0</balance>
      </to_account>
    </t_to_my_client>
    <amount_local>100.0</amount_local>
    <date_transaction>2023-01-01T00:00:00</date_transaction>
  </transaction>
</report>
"""


def _transactions():
    root = etree.fromstring(SAMPLE_XML)
    return root.findall("transaction")


def test_receivers_endpoint(monkeypatch):
    txs = _transactions()
    monkeypatch.setattr(gq, "load_transactions", lambda prefix=None: txs)
    app = gq.create_app()
    client = app.test_client()
    resp = client.get("/receivers")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data[0]["name"] == "Bob Receiver"
