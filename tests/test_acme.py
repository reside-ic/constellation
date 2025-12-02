import types

from constellation.acme import acme_buddy_container
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

    cfg = config_acme(data, "acme_buddy")
    assert cfg.email == "reside@imperial.ac.uk"
    assert cfg.dns_provider == "hdb"
    assert cfg.ref.repo == "ghcr.io/reside-ic"
    assert cfg.ref.name == "acme-buddy"
    assert cfg.ref.tag == "main"
    assert cfg.port == 2112
    assert cfg.env["HDB_ACME_USERNAME"] == "testuser"
    assert cfg.env["HDB_ACME_PASSWORD"] == "testpw"


def test_acme_buddy_config_cloudflare(monkeypatch):
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
        },
    }
    cfg = config_acme(data, "acme_buddy")
    assert cfg.email == "reside@imperial.ac.uk"
    assert cfg.dns_provider == "cloudflare"
    assert cfg.ref.repo == "ghcr.io/reside-ic"
    assert cfg.ref.name == "acme-buddy"
    assert cfg.ref.tag == "main"
    assert cfg.port == 2112
    assert cfg.additional_domains == ["anotherhost.com"]
    assert cfg.env["CLOUDFLARE_DNS_API_TOKEN"] == "abcdefgh12345678"
    assert cfg.env["ACME_BUDDY_STAGING"] == "0"


def test_acme_buddy_container():
    cfg = types.SimpleNamespace()
    cfg.containers = {"acme-buddy": "acme-buddy"}
    cfg.container_prefix = "prefix"
    cfg.hostname = "example.com"
    cfg.acme_buddy = types.SimpleNamespace(
        dns_provider="cloudflare",
        env={
            "CLOUDFLARE_DNS_API_TOKEN": "abcdefgh12345678",
            "ACME_BUDDY_STAGING": "0",
        },
        ref="ghcr.io/reside-ic/acme-buddy:main",
        port=2112,
        email="reside@imperial.ac.uk",
        additional_domains=["www.example.com"],
    )

    proxy = types.SimpleNamespace()
    proxy.name_external = lambda prefix: f"{prefix}-proxy"
    tls_volume = "tls-volume"
    acme = acme_buddy_container(
        cfg.acme_buddy,
        cfg.containers["acme-buddy"],
        proxy.name_external(cfg.container_prefix),
        tls_volume,
        cfg.hostname,
    )

    assert acme.environment["ACME_BUDDY_STAGING"] == "0"
    assert acme.environment["CLOUDFLARE_DNS_API_TOKEN"] == "abcdefgh12345678"
    assert acme.args[0] == "--domain"
    assert acme.args[1] == "example.com,www.example.com"
    assert acme.args[2] == "--email"
    assert acme.args[3] == "reside@imperial.ac.uk"
    assert acme.args[4] == "--certificate-path"
    assert acme.args[6] == "--key-path"
    assert acme.args[8] == "--account-path"
    assert acme.args[10] == "--reload-container"
    assert acme.args[11] == "prefix-proxy"
    assert acme.args[12] == "--dns-provider"
    assert acme.args[13] == "cloudflare"
