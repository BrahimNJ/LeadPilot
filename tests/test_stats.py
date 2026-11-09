from app.demo import seed_demo


def test_stats_on_an_empty_crm(client):
    assert client.get("/stats").json() == {
        "companies": 0,
        "contacts": 0,
        "open_deals": 0,
        "open_pipeline_amount": 0,
        "won_deals": 0,
        "lost_deals": 0,
        "win_rate": None,
    }


def test_stats_sum_open_deals_and_compute_the_win_rate(client, session):
    seed_demo(session)

    stats = client.get("/stats").json()

    assert stats["companies"] == 3
    assert stats["contacts"] == 5
    assert stats["open_deals"] == 3
    assert stats["open_pipeline_amount"] == 15000 + 8000 + 42000
    assert (stats["won_deals"], stats["lost_deals"]) == (1, 1)
    assert stats["win_rate"] == 0.5
