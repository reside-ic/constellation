from constellation.acme import AcmeBuddyConfig


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

    cfg = AcmeBuddyConfig(data)
    assert cfg.email == "reside@imperial.ac.uk"
    assert cfg.dns_provider == "hdb"
    assert cfg.hdb_username == "testuser"
    assert cfg.hdb_password == "testpw"
    assert cfg.ref.repo == "ghcr.io/reside-ic"
    assert cfg.ref.name == "acme-buddy"
    assert cfg.ref.tag == "main"
    assert cfg.port == 2112


def test_acme_buddy_config_cloudflare():
    data = {
        "acme_buddy": {
            "additional_domains": "anotherhost.com",
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
    cfg = AcmeBuddyConfig(data)
    assert cfg.email == "reside@imperial.ac.uk"
    assert cfg.dns_provider == "cloudflare"
    assert cfg.cloudflare_token == "abcdefgh12345678"
    assert cfg.ref.repo == "ghcr.io/reside-ic"
    assert cfg.ref.name == "acme-buddy"
    assert cfg.ref.tag == "main"
    assert cfg.port == 2112
    assert cfg.additional_domains == "anotherhost.com"
