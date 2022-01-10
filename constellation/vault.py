import os
import re

import hvac


def resolve_secret(value, client):
    re_vault = re.compile("^VAULT:([^:]+):([^:]+)$")
    if not value.startswith("VAULT:"):
        return False, value
    m = re_vault.match(value)
    if not m:
        raise Exception("Invalid vault accessor '{}'".format(value))
    path, key = m.groups()
    data = client.read(path)
    if not data:
        raise Exception("Did not find secret at '{}'".format(path))

    if key not in data["data"]:
        raise Exception("Did not find key '{}' at secret path '{}'".format(
            key, path))
    return True, data["data"][key]


def resolve_secrets(x, client):
    if not x:
        pass
    elif type(x) == dict:
        resolve_secrets_dict(x, client)
    else:
        resolve_secrets_object(x, client)


def resolve_secrets_object(obj, client):
    for k, v in vars(obj).items():
        if type(v) == str:
            updated, v = resolve_secret(v, client)
            if updated:
                setattr(obj, k, v)


def resolve_secrets_dict(d, client):
    for k, v, in d.items():
        if type(v) == str:
            updated, v = resolve_secret(v, client)
            if updated:
                d[k] = v


class vault_config:
    def __init__(self, url, auth_method, auth_args):
        self.url = url
        self.auth_method = auth_method
        self.auth_args = auth_args

    def client(self):
        if not self.url:
            return vault_not_enabled()
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
            print("Authenticating with the vault using '{}'".format(
                self.auth_method))

            if self.auth_method == "github":
                if not self.auth_args:
                    self.auth_args = {}
                if "token" not in self.auth_args:
                    self.auth_args["token"] = get_github_token()

            getattr(cl.auth, self.auth_method).login(**self.auth_args)
        return cl


class vault_not_enabled:
    def __getattr__(self, name):
        raise Exception("Vault access is not enabled")


def get_github_token():
    try:
        return os.environ["VAULT_AUTH_GITHUB_TOKEN"]
    except KeyError:
        return input("Enter GitHub token for vault: ").strip()


def drop_envvar(name):
    if name in os.environ:
        del os.environ[name]
