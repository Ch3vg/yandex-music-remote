from ym_remote.net.addresses import choose_network, filter_candidates


def test_address_priority_and_dropped_ranges():
    discovered = [
        "11.0.0.1",
        "10.0.0.2",
        "10.1.1.1",
        "192.168.1.10",
        "127.0.0.1",
        "169.254.1.1",
        "172.16.0.5",
        "172.31.255.1",
        "172.32.0.1",
        "8.8.8.8",
        "192.168.1.10",
    ]
    assert filter_candidates(discovered) == [
        "192.168.1.10",
        "10.0.0.2",
        "10.1.1.1",
        "11.0.0.1",
        "172.32.0.1",
        "8.8.8.8",
    ]


def test_local_ip_is_chosen_even_when_it_was_not_discovered():
    choice = choose_network(
        ["11.0.0.1", "192.168.1.10", "10.0.0.2"],
        local_ip="10.9.9.9",
        port=8001,
    )
    assert choice.chosen == "10.9.9.9"
    assert choice.all[0] == "10.9.9.9"
    assert "10.9.9.9" not in choice.candidates
    assert choice.url == "http://10.9.9.9:8001/"
    assert choice.info()["port"] == 8001


def test_known_local_ip_moves_to_the_front_without_a_duplicate():
    choice = choose_network(
        ["192.168.1.10", "10.0.0.2", "11.0.0.1"],
        local_ip="10.0.0.2",
        port=8001,
    )
    assert choice.all == ("10.0.0.2", "192.168.1.10", "11.0.0.1")
    assert choice.chosen == "10.0.0.2"


def test_empty_discovery_falls_back_to_loopback():
    choice = choose_network([], local_ip=None, port=8001)
    assert choice.chosen == "127.0.0.1"
    assert choice.all == ("127.0.0.1",)


def test_foreign_qr_ip_is_replaced_by_the_chosen_address():
    choice = choose_network(["192.168.1.10", "10.0.0.2"], local_ip="10.8.8.8", port=8001)
    assert choice.qr_host("8.8.8.8") == "10.8.8.8"
    assert choice.qr_host("192.168.1.10") == "192.168.1.10"
    assert choice.qr_host("10.8.8.8") == "10.8.8.8"
    assert choice.qr_host("172.16.0.9") == choice.chosen
    assert choice.qr_host(None) == choice.chosen
