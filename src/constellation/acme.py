import os

import constellation
from constellation.config import (
    config_dict,
    config_integer,
    config_list,
    config_string,
)


class AcmeBuddyConfig:
    def __init__(self, data, path: list[str]):
        name = config_string(data, [*path, "image", "name"])
        repo = config_string(data, [*path, "image", "repo"])
        tag = config_string(data, [*path, "image", "tag"])
        self.ref = constellation.ImageReference(repo, name, tag)
        self.port = config_integer(data, [*path, "port"])
        self.dns_provider = config_string(data, [*path, "dns_provider"], True)
        self.env = config_dict(data, [*path, "env"])
        if "ACME_BUDDY_STAGING" in os.environ:
            self.env["ACME_BUDDY_STAGING"] = os.environ["ACME_BUDDY_STAGING"]
        self.email = config_string(data, [*path, "email"])
        self.additional_domains = []
        if "additional_domains" in config_dict(data, path):
            self.additional_domains = config_list(
                data, [*path, "additional_domains"]
            )


def acme_buddy_container(
    cfg: AcmeBuddyConfig, name: str, proxy: str, volume: str, hostname: str
) -> constellation.ConstellationContainer:
    acme_mounts = [
        constellation.ConstellationVolumeMount(volume, "/tls"),
        constellation.ConstellationBindMount(
            "/var/run/docker.sock",
            "/var/run/docker.sock",
        ),
    ]

    domain_names = ",".join((hostname, *cfg.additional_domains))

    acme = constellation.ConstellationContainer(
        name,
        cfg.ref,
        ports=[cfg.port],
        mounts=acme_mounts,
        environment=cfg.env,
        args=[
            "--domain",
            domain_names,
            "--email",
            cfg.email,
            "--certificate-path",
            "/tls/certificate.pem",
            "--key-path",
            "/tls/key.pem",
            "--account-path",
            "/tls/account.json",
            "--reload-container",
            proxy,
        ]
        + (
            ["--dns-provider", cfg.dns_provider]
            if cfg.dns_provider is not None
            else []
        ),
    )
    return acme
