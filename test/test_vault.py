import os
import pytest

from unittest import mock

import vault_dev

from constellation.vault import *


def test_secret_reading():
    with vault_dev.server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")
        assert resolve_secret("foo", client) == (False, "foo")
        assert resolve_secret("VAULT:secret/foo:value", client) == \
            (True, "s3cret")


def test_secret_reading_of_dicts():
    with vault_dev.server() as s:
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


def test_secret_reading_of_objects():
    with vault_dev.server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")

        class Data:
            def __init__(self):
                self.foo = "VAULT:secret/foo:value"
                self.bar = "constant"

        dat = Data()
        resolve_secrets(dat, client)
        assert dat.foo == "s3cret"
        assert dat.bar == "constant"


def test_accessor_validation():
    with vault_dev.server() as s:
        client = s.client()
        with pytest.raises(Exception, match="Invalid vault accessor"):
            resolve_secret("VAULT:invalid", client)
        with pytest.raises(Exception, match="Invalid vault accessor"):
            resolve_secret("VAULT:invalid:a:b", client)


def test_error_for_missing_secret():
    with vault_dev.server() as s:
        client = s.client()
        msg = "Did not find secret at 'secret/foo'"
        with pytest.raises(Exception, match=msg):
            resolve_secret("VAULT:secret/foo:bar", client)


def test_error_for_missing_secret_key():
    with vault_dev.server() as s:
        client = s.client()
        client.write("secret/foo", value="s3cret")
        msg = "Did not find key 'bar' at secret path 'secret/foo'"
        with pytest.raises(Exception, match=msg):
            resolve_secret("VAULT:secret/foo:bar", client)


def test_vault_config():
    with vault_dev.server() as s:
        url = "http://localhost:{}".format(s.port)
        cfg = vault_config(url, "token", {"token": s.token})
        cl = cfg.client()
        assert cl.is_authenticated()


def test_vault_config_when_missing():
    cfg = vault_config(None, "token", {"token": "root"})
    cl = cfg.client()
    assert type(cl) == vault_not_enabled
    with pytest.raises(Exception, match="Vault access is not enabled"):
        cl.read("secret/foo")


# To run this test you will need a token for the vimc robot user -
# this can be found in the vimc vault as
# /secret/vimc-robot/vault-token
#
# This environment variable is configured on travis
def test_vault_config_login():
    if "VAULT_TEST_GITHUB_PAT" not in os.environ:
        pytest.skip("VAULT_TEST_GITHUB_PAT is not defined")
    with vault_dev.server() as s:
        cl = s.client()
        cl.sys.enable_auth_method(method_type="github")
        cl.write("auth/github/config", organization="vimc")

        url = "http://localhost:{}".format(s.port)
        token = os.environ["VAULT_TEST_GITHUB_PAT"]
        cfg = vault_config(url, "github", {"token": token})
        assert cfg.client().is_authenticated()


def test_vault_config_login_no_args():
    if "VAULT_TEST_GITHUB_PAT" not in os.environ:
        pytest.skip("VAULT_TEST_GITHUB_PAT is not defined")

    with vault_dev.server() as s:
        cl = s.client()
        cl.sys.enable_auth_method(method_type="github")
        cl.write("auth/github/config", organization="vimc")
        url = "http://localhost:{}".format(s.port)
        token = os.environ["VAULT_TEST_GITHUB_PAT"]
        with mock.patch.dict(os.environ, {"VAULT_AUTH_GITHUB_TOKEN": token}):
            cfg = vault_config(url, "github", None)
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
