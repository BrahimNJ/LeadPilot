from app.ratelimit import MAX_TRACKED_CLIENTS, RateLimiter


def test_requests_over_the_limit_get_a_wait_time():
    limiter = RateLimiter(limit=2)

    assert limiter.check("a", 60.0) == 0
    assert limiter.check("a", 61.0) == 0
    assert limiter.check("a", 75.0) == 45


def test_clients_are_counted_separately():
    limiter = RateLimiter(limit=1)

    assert limiter.check("a", 60.0) == 0
    assert limiter.check("b", 60.0) == 0


def test_a_new_window_starts_from_zero():
    limiter = RateLimiter(limit=1)
    limiter.check("a", 60.0)
    assert limiter.check("a", 119.0) > 0

    assert limiter.check("a", 120.0) == 0


def test_unknown_clients_share_a_bucket_once_the_table_is_full():
    limiter = RateLimiter(limit=1)
    for i in range(MAX_TRACKED_CLIENTS):
        limiter.check(str(i), 60.0)

    assert limiter.check("new-1", 60.0) == 0
    assert limiter.check("new-2", 60.0) > 0
    assert limiter.check("0", 60.0) > 0
