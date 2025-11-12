import types

import pytest

from constellation.acme import acme_buddy_container, acme_buddy_env
from constellation.config import config_acme


def test_acme_buddy_config_hdb():
    data = {
        "acme_buddy": {
            "email": "reside@imperial.ac.uk",
            "image": {
                "repo": "ghcr.io/reside-ic",
                "name": "acme-buddy",
                "tag": "main",
            },
            "port": 2112,
            "dns_provider": "hdb",
            "env": {
                "HDB_ACME_USERNAME": "testuser",
                "HDB_ACME_PASSWORD": "testpw",
            },
        },
    }

    cfg = config_acme(data)
    assert cfg.email == "reside@imperial.ac.uk"
    assert cfg.dns_provider == "hdb"
    assert cfg.hdb_username == "testuser"
    assert cfg.hdb_password == "testpw"
    assert cfg.ref.repo == "ghcr.io/reside-ic"
    assert cfg.ref.name == "acme-buddy"
    assert cfg.ref.tag == "main"
    assert cfg.port == 2112
    env = acme_buddy_env(cfg.dns_provider, cfg)
    assert env["HDB_ACME_USERNAME"] == cfg.hdb_username
    assert env["HDB_ACME_PASSWORD"] == cfg.hdb_password


def test_acme_buddy_config_cloudflare():
    data = {
        "acme_buddy": {
            "additional_domains": ["anotherhost.com"],
            "email": "reside@imperial.ac.uk",
            "image": {
                "repo": "ghcr.io/reside-ic",
                "name": "acme-buddy",
                "tag": "main",
            },
            "port": 2112,
            "dns_provider": "cloudflare",
            "env": {
                "CLOUDFLARE_DNS_API_TOKEN": "abcdefgh12345678",
            },
        },
    }
    cfg = config_acme(data)
    assert cfg.email == "reside@imperial.ac.uk"
    assert cfg.dns_provider == "cloudflare"
    assert cfg.cloudflare_token == "abcdefgh12345678"
    assert cfg.ref.repo == "ghcr.io/reside-ic"
    assert cfg.ref.name == "acme-buddy"
    assert cfg.ref.tag == "main"
    assert cfg.port == 2112
    assert cfg.additional_domains == ["anotherhost.com"]
    env = acme_buddy_env(cfg.dns_provider, cfg)
    assert env["CLOUDFLARE_DNS_API_TOKEN"] == cfg.cloudflare_token


def test_acme_buddy_bad_provider():
    data = {
        "acme_buddy": {
            "additional_domains": ["anotherhost.com"],
            "email": "reside@imperial.ac.uk",
            "image": {
                "repo": "ghcr.io/reside-ic",
                "name": "acme-buddy",
                "tag": "main",
            },
            "port": 2112,
            "dns_provider": "anotherdns",
            "env": {
                "ANOTHER_API_TOKEN": "abcdefgh12345678",
            },
        },
    }
    with pytest.raises(
        ValueError, match="Unrecognised DNS provider: anotherdns"
    ):
        _cfg = config_acme(data)

    with pytest.raises(
        ValueError, match="Unrecognised DNS provider: anotherdns"
    ):
        _env = acme_buddy_env("anotherdns", data)


def test_acme_buddy_container(monkeypatch):
    monkeypatch.setenv("ACME_BUDDY_STAGING", "0")
    data = {
        "acme_buddy": {
            "additional_domains": ["anotherhost.com"],
            "email": "reside@imperial.ac.uk",
            "image": {
                "repo": "ghcr.io/reside-ic",
                "name": "acme-buddy",
                "tag": "main",
            },
            "port": 2112,
            "dns_provider": "cloudflare",
            "env": {
                "CLOUDFLARE_DNS_API_TOKEN": "abcdefgh12345678",
            },
        }
    }

    acme_cfg = config_acme(data)
    cfg = types.SimpleNamespace()
    cfg.containers = {"acme-buddy": "acme-buddy"}
    cfg.container_prefix = "prefix"
    cfg.hostname = "example.com"
    cfg.acme_buddy = types.SimpleNamespace(
        dns_provider = "cloudflare",
        cloudflare_token = "abcdefgh12345678",
        ref = "ghcr.io/reside-ic/acme-buddy:main",
        port = 2112,
        email = "reside@imperial.ac.uk",
        additional_domains=["www.example.com"],
    )

    proxy = types.SimpleNamespace()
    proxy.name_external = lambda prefix: f"{prefix}-proxy"
    tls_volume = "tls-volume"
    acme = acme_buddy_container(cfg, proxy, tls_volume)

    assert acme.environment["ACME_BUDDY_STAGING"] == 0
    assert acme.environment["CLOUDFLARE_DNS_API_TOKEN"] == "abcdefgh12345678"
    assert acme.args[0] == "--domain"
    assert acme.args[1] == "example.com,www.example.com"
    assert acme.args[2] == "--email"
    assert acme.args[3] == "reside@imperial.ac.uk"
    assert acme.args[4] == "--dns-provider"
    assert acme.args[5] == "cloudflare"
    assert acme.args[-1] == "prefix-proxy"

