from sources import Prospect, normalize_domain, dedupe_key, parse_csv_prospects


def test_normalize_domain():
    assert normalize_domain("https://WWW.Example.com/path") == "example.com"


def test_dedupe_prefers_source_id():
    prospect = Prospect(name="Acme", source="directory", source_external_id="123", email="x@example.com")
    assert dedupe_key(prospect) == ("source_id", "directory:123")


def test_dedupe_falls_back_to_domain():
    prospect = Prospect(name="Acme", website_url="https://www.example.com")
    assert dedupe_key(prospect) == ("domain", "example.com")


def test_parse_csv_prospects():
    rows = parse_csv_prospects("name,website,email\nAcme,https://acme.test,a@acme.test")
    assert rows[0].name == "Acme"
    assert rows[0].website_url == "https://acme.test"
    assert rows[0].email == "a@acme.test"
