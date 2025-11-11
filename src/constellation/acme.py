

def acme_buddy_container(cfg, proxy, tls_volume):
    name = cfg.containers["acme-buddy"]
    acme_buddy_staging = int(os.environ.get("ACME_BUDDY_STAGING", "0"))
    acme_env = {
        "ACME_BUDDY_STAGING": acme_buddy_staging,
        "HDB_ACME_USERNAME": cfg.acme_buddy_hdb_username,
        "HDB_ACME_PASSWORD": cfg.acme_buddy_hdb_password,
    }
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
            "hdb",
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
