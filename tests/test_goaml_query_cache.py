from datetime import datetime
from tools.goaml_query import load_transactions

SAMPLE_XML = """
<report>
  <transaction>
    <amount_local>5</amount_local>
  </transaction>
</report>
"""

def test_load_transactions_uses_cache(monkeypatch, tmp_path):
    called = {"list": 0, "download": 0}

    class Blob:
        name = "folder/report.xml"
        time_created = datetime(2024, 1, 1)

        def download_as_bytes(self):
            called["download"] += 1
            return SAMPLE_XML.encode()

    class Bucket:
        def list_blobs(self, prefix=None):
            called["list"] += 1
            return [Blob()]

    class Client:
        def bucket(self, name):
            return Bucket()

    monkeypatch.setenv("GOAML_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("tools.goaml_query._get_storage_client", lambda: Client())

    # First call downloads the XML
    txs = load_transactions(prefix="folder")
    assert len(txs) == 1
    assert called["download"] == 1
    assert called["list"] == 1

    # Second call uses the cache and avoids extra downloads/listings
    txs = load_transactions(prefix="folder")
    assert len(txs) == 1
    assert called["download"] == 1
    assert called["list"] == 1
