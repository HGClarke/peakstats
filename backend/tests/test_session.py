from app.session import read_session, sign_session


def test_round_trip_returns_athlete_id():
    token = sign_session(12345, "secret")
    assert read_session(token, "secret") == 12345


def test_wrong_secret_returns_none():
    token = sign_session(12345, "secret")
    assert read_session(token, "other-secret") is None


def test_tampered_token_returns_none():
    token = sign_session(12345, "secret")
    assert read_session(token + "x", "secret") is None


def test_expired_token_returns_none():
    token = sign_session(12345, "secret")
    assert read_session(token, "secret", max_age=-1) is None
