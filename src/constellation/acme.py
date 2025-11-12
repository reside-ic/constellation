import os

import constellation
from constellation.config import config_integer, config_list, config_string


class AcmeBuddyConfig:
    def __init__(self, data):
        name = config_string(data, ["acme_buddy", "image", "name"])
        repo = config_string(data, ["acme_buddy", "image", "repo"])
        tag = config_string(data, ["acme_buddy", "image", "tag"])
        self.ref = constellation.ImageReference(repo, name, tag)

        self.port = config_integer(data, ["acme_buddy", "port"])
        self.dns_provider = config_string(data, ["acme_buddy", "dns_provider"])

        if self.dns_provider == "hdb":
            self.hdb_username = config_string(
                data, ["acme_buddy", "env", "HDB_ACME_USERNAME"]
            )
            self.hdb_password = config_string(
                data, ["acme_buddy", "env", "HDB_ACME_PASSWORD"]
            )
        elif self.dns_provider == "cloudflare":
            self.cloudflare_token = config_string(
                data, ["acme_buddy", "env", "CLOUDFLARE_DNS_API_TOKEN"]
            )
        else:
            err = f"Unrecognised DNS provider: {self.dns_provider}"
            raise ValueError(err)

        self.email = config_string(data, ["acme_buddy", "email"])
        if "additional_domains" in data["acme_buddy"]:
            self.additional_domains = config_list(
                data, ["acme_buddy", "additional_domains"]
            )


def acme_buddy_env(dns_provider, acme_buddy_cfg):
    staging = int(os.environ.get("ACME_BUDDY_STAGING", "0"))
    acme_env = {"ACME_BUDDY_STAGING": staging}

    if dns_provider == "hdb":
        acme_env.update(
            {
                "HDB_ACME_USERNAME": acme_buddy_cfg.hdb_username,
                "HDB_ACME_PASSWORD": acme_buddy_cfg.hdb_password,
            }
        )
    elif dns_provider == "cloudflare":
        acme_env.update(
            {"CLOUDFLARE_DNS_API_TOKEN": acme_buddy_cfg.cloudflare_token}
        )
    return acme_env


def acme_buddy_container(cfg, proxy, tls_volume):
    name = cfg.containers["acme-buddy"]
    dns_provider = cfg.acme_buddy.dns_provider
    acme_env = acme_buddy_env(dns_provider, cfg.acme_buddy)

    acme_mounts = [
        constellation.ConstellationVolumeMount(tls_volume, "/tls"),
        constellation.ConstellationBindMount(
            "/var/run/docker.sock",
            "/var/run/docker.sock",
        ),
    ]

    domain_names = ",".join((cfg.hostname, *cfg.acme_buddy.additional_domains))

    acme = constellation.ConstellationContainer(
        name,
        cfg.acme_buddy.ref,
        ports=[cfg.acme_buddy.port],
        mounts=acme_mounts,
        environment=acme_env,
        args=[
            "--domain",
            domain_names,
            "--email",
            cfg.acme_buddy.email,
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
