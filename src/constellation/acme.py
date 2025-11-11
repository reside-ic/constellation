from config import config_integer, config_string, config_list
from constellation import ImageReference

class AcmeConfig:
    def __init__(self, data):
        image_name = config.config_string(["acme_buddy", "name"])
        image_repo = config.config_string(["acme_buddy", "repo"])
        image_tag = config.config_string(["acme_buddy", "tag"])
        self.acme_buddy_ref = constellation.ImageReference(repo, name, tag)

        self.acme_buddy_port = config.config_integer(dat, ["acme_buddy", "port"])
        self.acme_buddy_dns_provider = config.config_string(dat, ["acme_buddy", "dns_provider"])
        if self.acme_buddy_dns_provider == "hdb":
            self.acme_buddy_hdb_username = config.config_string(dat, ["acme_buddy", "env", "HDB_ACME_USERNAME"])
            self.acme_buddy_hdb_username = config.config_string(dat, ["acme_buddy", "env", "HDB_ACME_PASSWORD"])
        elif self.acme_buddy_dns_provider == "cloudflare":
            self.acme_buddy_cloudflare_token = config.config_string(dat, ["acme_buddy", "env", "CLOUDFLARE_DNS_API_TOKEN"])
        else:
            raise ValueError(f"Unrecognised DNS provider: {self.acme_buddy_dns_provider}")

        self.acme_buddy_email = config.config_string(dat, ["acme_buddy", "email"])
        self.acme_additional_domains = config.config_list(dat, ["acme_buddy", "additional_domains"])


def acme_buddy_env(dns_provider, cfg):
    acme_buddy_staging = int(os.environ.get("ACME_BUDDY_STAGING", "0"))
    acme_env = {"ACME_BUDDY_STAGING": acme_buddy_staging}

    if dns_provider == "hdb":
        acme_env.update({
            "HDB_ACME_USERNAME": cfg.acme_buddy_hdb_username,
            "HDB_ACME_PASSWORD": cfg.acme_buddy_hdb_password,
        })
    elif dns_provider == "cloudflare":
        acme_env.update({
            "CLOUDFLARE_DNS_API_TOKEN": cfg.acme_buddy_cloudflare_token
        })s
    return acme_env


def acme_buddy_container(cfg, proxy, tls_volume):
    name = cfg.containers["acme-buddy"]
    dns_provider = cfg.acme_buddy_dns_provider
    acme_env = acme_buddy_env(dns_provider, cfg)

    acme_mounts = [
        constellation.ConstellationVolumeMount(tls_volume, "/tls"),
        constellation.ConstellationBindMount("/var/run/docker.sock", "/var/run/docker.sock"),
    ]

    domain_names = ",".join([cfg.hostname] + cfg.acme_additional_domains)

    acme = constellation.ConstellationContainer(
        name,
        cfg.acme_buddy_ref,
        ports=[cfg.acme_buddy_port],
        mounts=acme_mounts,
        environment=acme_env,
        args=[
            "--domain",
            domain_names,
            "--email",
            cfg.acme_buddy_email,
            "--dns-provider",
            dns_provider,
            "--certificate-path",
            "/tls/certificate.pem",
            "--key-path",
            "/tls/key.pem",
            "--account-path",
            "/tls/account.json",
            "--reload-container",
            proxy.name_external(cfg.container_prefix),
        ],
    )
    return acme
