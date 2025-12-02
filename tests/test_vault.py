import os
from dataclasses import dataclass
from unittest import mock

import pytest
import vault_dev

from constellation.vault import (
    VaultConfig,
    VaultNotEnabled,
    drop_envvar,
    get_github_token,
    resolve_secret,
    resolve_secrets,
)


def test_secret_reading():
    with vault_dev.Server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")
        assert resolve_secret("foo", client) == (False, "foo")
        assert resolve_secret("VAULT:secret/foo:value", client) == (
            True,
            "s3cret",
        )


def test_secret_reading_of_dicts():
    with vault_dev.Server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")
        # With data
        dat = {"foo": "VAULT:secret/foo:value", "bar": "constant"}
        resolve_secrets(dat, client)
        assert dat == {"foo": "s3cret", "bar": "constant"}
        # Without
        empty = {}
        resolve_secrets(empty, client)
        assert empty == {}


def test_secret_reading_of_dicts_recursive():
    with vault_dev.Server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")
        # With data
        dat = {"foo": {"bar": {"fizz": "VAULT:secret/foo:value"}}}
        resolve_secrets(dat, client)
        assert dat == {"foo": {"bar": {"fizz": "s3cret"}}}
        # Without
        empty = {}
        resolve_secrets(empty, client)
        assert empty == {}


def test_secret_reading_of_objects():
    with vault_dev.Server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")

        class Data:
            def __init__(self):
                self.foo = "VAULT:secret/foo:value"
                self.bar = "constant"
                self.fizz = {"secret": "VAULT:secret/foo:value"}

        dat = Data()
        resolve_secrets(dat, client)
        assert dat.foo == "s3cret"
        assert dat.bar == "constant"
        assert dat.fizz == {"secret": "s3cret"}


def test_secret_reading_of_nested_dataclass():
    with vault_dev.Server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")

        @dataclass
        class Nested:
            value: str

        @dataclass
        class Data:
            nested: Nested

        dat = Data(Nested("VAULT:secret/foo:value"))
        resolve_secrets(dat, client)
        assert dat.nested.value == "s3cret"


def test_accessor_validation():
    with vault_dev.Server() as s:
        client = s.client()
        with pytest.raises(Exception, match="Invalid vault accessor"):
            resolve_secret("VAULT:invalid", client)
        with pytest.raises(Exception, match="Invalid vault accessor"):
            resolve_secret("VAULT:invalid:a:b", client)


def test_error_for_missing_secret():
    with vault_dev.Server() as s:
        client = s.client()
        msg = "Did not find secret at 'secret/foo'"
        with pytest.raises(Exception, match=msg):
            resolve_secret("VAULT:secret/foo:bar", client)


def test_error_for_missing_secret_key():
    with vault_dev.Server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")
        msg = "Did not find key 'bar' at secret path 'secret/foo'"
        with pytest.raises(Exception, match=msg):
            resolve_secret("VAULT:secret/foo:bar", client)


def test_vault_config():
    with vault_dev.Server() as s:
        url = f"http://localhost:{s.port}"
        cfg = VaultConfig(url, "token", {"token": s.token})
        cl = cfg.client()
        assert cl.is_authenticated()


def test_vault_config_when_missing():
    cfg = VaultConfig(None, "token", {"token": "root"})
    cl = cfg.client()
    assert isinstance(cl, VaultNotEnabled)
    with pytest.raises(Exception, match="Vault access is not enabled"):
        cl.read("secret/foo")


# To run this test you will need a token for the vimc robot user -
# this can be found in the vimc vault as
# /secret/vimc-robot/github-pat
#
# This environment variable is configured on GitHub actions see usage details
# https://mrc-ide.myjetbrains.com/youtrack/articles/RESIDE-A-18/Vault#keys
def test_vault_config_login():
    pytest.skip(
        "Skipping test temporary, ticket to resolve this:"
        "https://mrc-ide.myjetbrains.com/youtrack/issue"
        "/RESIDE-351/Vault-login-testing-with-GitHub-authentication"
    )

    if "VAULT_TEST_GITHUB_PAT" not in os.environ:
        pytest.skip("VAULT_TEST_GITHUB_PAT is not defined")
    with vault_dev.Server() as s:
        cl = s.client()
        cl.sys.enable_auth_method(method_type="github")
        cl.write("auth/github/config", organization="vimc")

        url = f"http://localhost:{s.port}"
        token = os.environ["VAULT_TEST_GITHUB_PAT"]
        cfg = VaultConfig(url, "github", {"token": token})
        assert cfg.client().is_authenticated()


def test_vault_config_login_no_args():
    pytest.skip(
        "Skipping test temporary, ticket to resolve this:"
        "https://mrc-ide.myjetbrains.com/youtrack/issue"
        "/RESIDE-351/Vault-login-testing-with-GitHub-authentication"
    )

    if "VAULT_TEST_GITHUB_PAT" not in os.environ:
        pytest.skip("VAULT_TEST_GITHUB_PAT is not defined")

    with vault_dev.Server() as s:
        cl = s.client()
        cl.sys.enable_auth_method(method_type="github")
        cl.write("auth/github/config", organization="vimc")
        url = f"http://localhost:{s.port}"
        token = os.environ["VAULT_TEST_GITHUB_PAT"]
        with mock.patch.dict(os.environ, {"VAULT_AUTH_GITHUB_TOKEN": token}):
            cfg = VaultConfig(url, "github", None)
            assert cfg.client().is_authenticated()


# Utility required to work around https://github.com/hvac/hvac/issues/421
def test_drop_envvar_removes_envvar():
    name = "VAULT_DEV_TEST_VAR"
    os.environ[name] = "x"
    drop_envvar(name)
    assert name not in os.environ


def test_drop_envvar_ignores_missing_envvar():
    name = "VAULT_DEV_TEST_VAR"
    drop_envvar(name)
    assert name not in os.environ


def test_prompt_for_token():
    if "VAULT_TEST_GITHUB_PAT" not in os.environ:
        pytest.skip("VAULT_TEST_GITHUB_PAT is not defined")
    if "VAULT_AUTH_GITHUB_TOKEN" in os.environ:
        del os.environ["VAULT_AUTH_GITHUB_TOKEN"]
    pat = os.environ["VAULT_TEST_GITHUB_PAT"]
    with mock.patch("builtins.input", return_value=pat):
        assert get_github_token() == pat
