from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SESSION_COOKIE = "ps_session"
STATE_COOKIE = "ps_oauth_state"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days, in seconds


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="ps-session")


def sign_session(athlete_id: int, secret: str) -> str:
    return _serializer(secret).dumps({"athlete_id": athlete_id})


def read_session(
    token: str, secret: str, max_age: int = SESSION_MAX_AGE
) -> int | None:
    try:
        data = _serializer(secret).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return int(data["athlete_id"])
