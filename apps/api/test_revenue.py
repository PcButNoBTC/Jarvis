from revenue import money

def test_money_handles_decimal_and_none():
    assert money(None) == 0.0
    assert money("12.50") == 12.5
