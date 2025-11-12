import pytest

from constellation.acme import acme_buddy_env
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
