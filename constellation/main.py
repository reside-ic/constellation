import datetime
import json
import sys
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from typing import Any

import acme
import dns.resolver
import requests
from requests.auth import HTTPBasicAuth
from simple_acme_dns import ACMEClient

RENEWAL_TIME = timedelta(days=30)
LETSENCRYPT_PRODUCTION_URL = "https://acme-v02.api.letsencrypt.org/directory"
LETSENCRYPT_STAGING_URL = "https://acme-staging-v02.api.letsencrypt.org/directory"


class CloudflareProvider:
    def __init__(self, api_token, zone_id):
        self.api_token = api_token
        self.zone_id = zone_id

    @contextmanager
    def present(self, domain: str, token: str):
        headers = {"Authorization": f"Bearer {self.api_token}"}
        r = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{self.zone_id}/dns_records",
            json={
                "name": domain,
                "type": "TXT",
                "content": json.dumps(token),
                "comment": "ACME DNS-01 challenge",
            },
            headers=headers,
        )
        r.raise_for_status()
        record = r.json()["result"]["id"]

        try:
            yield
        finally:
            r = requests.delete(
                f"https://api.cloudflare.com/client/v4/zones/{self.zone_id}/dns_records/{record}",
                headers=headers,
            )
            r.raise_for_status()


class HdbAcmeProvider:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    @contextmanager
    def present(self, domain: str, token: str):
        url = f"https://hdb.ic.ac.uk/api/acme/v0/{domain}/auth_token"
        auth = HTTPBasicAuth(self.username, self.password)
        body = {"token": json.dumps(token)}
        r = requests.put(url, auth=auth, json=body)
        r.raise_for_status()
        try:
            yield
        finally:
            r = requests.delete(url, auth=auth, json=body)
            r.raise_for_status()


PROVIDERS = {
    "hdb-acme": HdbAcmeProvider,
    "cloudflare": CloudflareProvider,
}


# simple_acme_dns has this feature, but it does not handle CNAMEs correctly,
# which we need for HDB-ACME.
def check_propagation(domain, tokens, nameservers, timeout=300, interval=5):
    tokens = set(tokens)
    deadline = time.monotonic() + timeout
    resolver = dns.resolver.Resolver()
    if nameservers is not None:
        resolver.nameservers = nameservers
    while time.monotonic() < deadline:
        try:
            answers = resolver.resolve(domain, "TXT")
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            answers = []

        values = {rdata.strings[0].decode() for rdata in answers}
        missing = tokens.difference(values)
        if not missing:
            break

        print(
            f"Could not find tokens {list(missing)!r} in {list(values)!r} for {domain!r}"
        )
        time.sleep(interval)
    else:
        raise ValueError("DNS did not propagate in time")


def request_certificate(
    domains: list[str],
    email: str,
    server: str,
    provider: str,
    args: dict[str, Any],
    nameservers=None,
):
    client = ACMEClient(
        domains,
        email,
        server,
        new_account=True,
        generate_csr=True,
        nameservers=nameservers,
    )
    provider = PROVIDERS[provider](**args)

    with ExitStack() as stack:
        verification = client.request_verification_tokens()
        for domain, tokens in verification.items():
            for token in tokens:
                print(f"Configuring DNS record for {domain!r}")
                stack.enter_context(provider.present(domain, token))
                stack.callback(print, f"Cleaning up DNS record for {domain!r}")

        print("Waiting for DNS propagation...")
        for domain, tokens in verification.items():
            check_propagation(domain, tokens, nameservers)

        print("DNS propagation complete, requesting certificate...")
        try:
            certificate = client.request_certificate()
        except acme.errors.ValidationError as e:
            for authz in e.failed_authzrs:
                for c in authz.body.challenges:
                    print(c.error.detail)
            sys.exit(1)

        print("Got certificate!")
        return (client.certificate, client.private_key)


def load_existing_certificate(path: Path, domains: list[str]):
    try:
        chain_pem = (path / "chain.pem").read_bytes()
        key_pem = (path / "key.pem").read_bytes()
    except FileNotFoundError:
        return None

    chain = load_pem_x509_certificates(chain_pem)

    remaining_time = datetime.now() - chain[0].not_valid_after_utc
    if remaining_time < RENEWAL_TIME:
        return None

    return (chain_pem, key_pem)


def fetch_certificate(path: Path, *, domains: list[str], **kwargs):
    path.mkdir(parents=True, exist_ok=True)
    primary = domains[0]

    if (result := load_existing_certificate(path / primary)) is not None:
        return result

    # TODO: reuse account

    (chain_pem, key_pem) = request_certificate(domains, **kwargs)


def main():
    (cert, key) = request_certificate(
        ["montagu.vaccineimpact.org"],
        "reside@imperial.ac.uk",
        LETSENCRYPT_STAGING_URL,
        "cloudflare",
        {
            "zone_id": "CHANGEME",
            "api_token": "CHANGEME",
        },
        nameservers=["1.1.1.1"],
    )
    # (cert, key) = request_certificate(
    #     ["packit-dev.dide.ic.ac.uk"],
    #     "reside@imperial.ac.uk",
    #     "https://acme-staging-v02.api.letsencrypt.org/directory",
    #     "hdb-acme",
    #     {
    #         "username": "dide",
    #         "password": "CHANGEME",
    #     },
    #     # This is ns0.ic.ac.uk.
    #     nameservers = ["155.198.142.80"],
    # )


if __name__ == "__main__":
    for i in range(10):
        main()
