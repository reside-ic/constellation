import os
import re
from dataclasses import is_dataclass

import hvac


# is_dataclass is weird and returns true on both the actual class and
# instances of it.
#
# See https://docs.python.org/3/library/dataclasses.html#dataclasses.is_dataclass
def is_dataclass_instance(obj):
    return is_dataclass(obj) and not isinstance(obj, type)


def resolve_secret(value, client):
    re_vault = re.compile("^VAULT:([^:]+):([^:]+)$")
    if not value.startswith("VAULT:"):
        return False, value
    m = re_vault.match(value)
    if not m:
        msg = f"Invalid vault accessor '{value}'"
        raise Exception(msg)
    path, key = m.groups()
    data = client.read(path)
    if not data:
        msg = f"Did not find secret at '{path}'"
        raise Exception(msg)

    if key not in data["data"]:
        msg = f"Did not find key '{key}' at secret path '{path}'"
        raise Exception(msg)
    return True, data["data"][key]


def resolve_secrets(x, client):
    if not x:
        pass
    elif isinstance(x, dict):
        resolve_secrets_dict(x, client)
    else:
        resolve_secrets_object(x, client)


def resolve_secrets_object(obj, client):
    for k, v in vars(obj).items():
        if isinstance(v, str):
            updated, value = resolve_secret(v, client)
            if updated:
                setattr(obj, k, value)

        if isinstance(v, dict):
            resolve_secrets_dict(v, client)

        if is_dataclass_instance(v):
            resolve_secrets_object(v, client)


def resolve_secrets_dict(d, client):
    for (
        k,
        v,
    ) in d.items():
        if isinstance(v, str):
            updated, value = resolve_secret(v, client)
            if updated:
                d[k] = value
        elif isinstance(v, dict):
            resolve_secrets_dict(v, client)


class VaultConfig:
    def __init__(self, url, auth_method, auth_args):
        self.url = url
        self.auth_method = auth_method
        self.auth_args = auth_args

    def client(self):
        if not self.url:
            return VaultNotEnabled()
        # NOTE: we might actually try and pick up VAULT_TOKEN from the
        # environment, but can't let that value override any value
        # passed here.
        # See for this workaround https://github.com/hvac/hvac/issues/421
        drop_envvar("VAULT_ADDR")
        drop_envvar("VAULT_TOKEN")

        if self.auth_method == "token":
            cl = hvac.Client(url=self.url, token=self.auth_args["token"])
        else:
            cl = hvac.Client(url=self.url)
            print(f"Authenticating with the vault using '{self.auth_method}'")

            if self.auth_method == "github":
                if not self.auth_args:
                    self.auth_args = {}
                if "token" not in self.auth_args:
                    self.auth_args["token"] = get_github_token()

            getattr(cl.auth, self.auth_method).login(**self.auth_args)
        return cl


class VaultNotEnabled:
    def __getattr__(self, name):
        msg = "Vault access is not enabled"
        raise Exception(msg)


def get_github_token():
    try:
        return os.environ["VAULT_AUTH_GITHUB_TOKEN"]
    except KeyError:
        return input("Enter GitHub token for vault: ").strip()


def drop_envvar(name):
    if name in os.environ:
        del os.environ[name]
