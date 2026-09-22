from security import authorized


def test_security_is_open_when_no_key_is_configured():
    assert authorized(None) is True
