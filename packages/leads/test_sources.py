from sources import Prospect, normalize_domain, dedupe_key


def test_normalize_domain():
    assert normalize_domain("https://WWW.Example.com/path") == "example.com"


def test_dedupe_prefers_source_id():
    prospect = Prospect(name="Acme", source="directory", source_external_id="123", email="x@example.com")
    assert dedupe_key(prospect) == ("source_id", "directory:123")


def test_dedupe_falls_back_to_domain():
    prospect = Prospect(name="Acme", website_url="https://www.example.com")
    assert dedupe_key(prospect) == ("domain", "example.com")
