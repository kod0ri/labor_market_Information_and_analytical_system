"""Регресійні тести на визначення IP клієнта (src/api/ratelimit.py).

Головний інваріант безпеки: клієнт НЕ може підробити ключ rate-limiter через
заголовки. Раніше get_client_ip довіряв cf-connecting-ip і першому елементу
X-Forwarded-For — обидва повністю підконтрольні клієнту → обхід ліміту логіну.
"""

from types import SimpleNamespace

import src.api.ratelimit as rl


def _req(xff=None, cf=None, peer="10.0.0.9"):
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    if cf is not None:
        headers["cf-connecting-ip"] = cf
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_spoofed_prefix_ignored(monkeypatch):
    # 1 довірений проксі: беремо ХВІСТ XFF (доданий проксі), не префікс клієнта.
    monkeypatch.setattr(rl, "_TRUSTED_PROXY_HOPS", 1)
    ip = rl.get_client_ip(_req(xff="1.2.3.4, 203.0.113.7"))
    assert ip == "203.0.113.7"


def test_cf_header_not_trusted_by_default(monkeypatch):
    monkeypatch.setattr(rl, "_TRUSTED_PROXY_HOPS", 1)
    monkeypatch.setattr(rl, "_TRUST_CF_HEADER", False)
    ip = rl.get_client_ip(_req(xff="203.0.113.7", cf="6.6.6.6"))
    assert ip == "203.0.113.7"  # cf-заголовок проігноровано


def test_cf_header_used_when_explicitly_trusted(monkeypatch):
    monkeypatch.setattr(rl, "_TRUST_CF_HEADER", True)
    ip = rl.get_client_ip(_req(xff="203.0.113.7", cf="9.9.9.9"))
    assert ip == "9.9.9.9"


def test_two_hops(monkeypatch):
    # Caddy → nginx: реальний клієнт — другий з хвоста.
    monkeypatch.setattr(rl, "_TRUSTED_PROXY_HOPS", 2)
    ip = rl.get_client_ip(_req(xff="1.2.3.4, 203.0.113.7, 172.16.0.2"))
    assert ip == "203.0.113.7"


def test_falls_back_to_peer_without_proxy(monkeypatch):
    monkeypatch.setattr(rl, "_TRUSTED_PROXY_HOPS", 1)
    assert rl.get_client_ip(_req()) == "10.0.0.9"


def test_short_xff_falls_back_to_peer(monkeypatch):
    # Заявлено 2 проксі, але у XFF лише 1 запис → не довіряємо, беремо peer.
    monkeypatch.setattr(rl, "_TRUSTED_PROXY_HOPS", 2)
    assert rl.get_client_ip(_req(xff="1.2.3.4")) == "10.0.0.9"
