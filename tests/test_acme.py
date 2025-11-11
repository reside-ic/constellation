from constellation.acme import (
    AcmeConfig
)


def test_acme_config_hdb():
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
                "HDB_ACME_PASSWORD": "testpw"
            },
        },
    }
    
    cfg = AcmeConfig(data)
    assert cfg.acme_buddy_email == "reside@imperial.ac.uk"
    assert cfg.acme_buddy_dns_provider == "hdb"
    assert cfg.acme_buddy_hdb_username == "testuser"
    assert cfg.acme_buddy_hdb_password == "testpw"
    assert cfg.acme_buddy_ref.repo == "ghcr.io/reside-ic"
    assert cfg.acme_buddy_ref.name == "acme-buddy"
    assert cfg.acme_buddy_ref.tag == "main"
    assert cfg.acme_buddy_port == 2112



def test_acme_config_cloudflare():
    data = {
        "acme_buddy": {
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
    cfg = AcmeConfig(data)
    assert cfg.acme_buddy_email == "reside@imperial.ac.uk"
    assert cfg.acme_buddy_dns_provider == "cloudflare"
    assert cfg.acme_buddy_cloudflare_token == "abcdefgh12345678"
    assert cfg.acme_buddy_ref.repo == "ghcr.io/reside-ic"
    assert cfg.acme_buddy_ref.name == "acme-buddy"
    assert cfg.acme_buddy_ref.tag == "main"
    assert cfg.acme_buddy_port == 2112
