import os

import constellation
from constellation.config import (
    config_dict,
    config_integer,
    config_list,
    config_string,
)


class AcmeBuddyConfig:
    def __init__(self, data):
        name = config_string(data, ["acme_buddy", "image", "name"])
        repo = config_string(data, ["acme_buddy", "image", "repo"])
        tag = config_string(data, ["acme_buddy", "image", "tag"])
        self.ref = constellation.ImageReference(repo, name, tag)
        self.port = config_integer(data, ["acme_buddy", "port"])
        self.dns_provider = config_string(data, ["acme_buddy", "dns_provider"])
        self.env = config_dict(data, ["acme_buddy", "env"])
        if "ACME_BUDDY_STAGING" in os.environ:
            self.env["ACME_BUDDY_STAGING"] = os.environ["ACME_BUDDY_STAGING"]
        self.email = config_string(data, ["acme_buddy", "email"])
        if "additional_domains" in data["acme_buddy"]:
            self.additional_domains = config_list(
                data, ["acme_buddy", "additional_domains"]
            )


def acme_buddy_container(cfg, proxy, tls_volume):
    name = cfg.containers["acme-buddy"]
    dns_provider = cfg.acme_buddy.dns_provider

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
        environment=cfg.acme_buddy.env,
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
