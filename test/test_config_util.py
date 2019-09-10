import pytest

from constellation.config_util import *

sample_data = {"a": "value1", "b": {"x": "value2"}, "c": 1, "d": True,
               "e": None}


def test_config_string_reads_simple_values():
    assert config_string(sample_data, "a") == "value1"
    assert config_string(sample_data, ["a"]) == "value1"


def test_config_string_reads_nested_values():
    assert config_string(sample_data, ["b", "x"]) == "value2"


def test_config_string_throws_on_missing_keys():
    with pytest.raises(KeyError):
        config_string(sample_data, "x")
    with pytest.raises(KeyError):
        config_string(sample_data, ["b", "y"])


def test_config_none_is_missing():
    with pytest.raises(KeyError):
        config_string(sample_data, ["e"], False)
    assert config_string(sample_data, ["e"], True) is None


def test_config_string_validates_types():
    with pytest.raises(ValueError):
        config_string(sample_data, "c")


def test_config_string_default():
    assert config_string(sample_data, "x", True) is None


def test_config_integer():
    assert config_integer(sample_data, "c") == 1


def test_config_boolean():
    assert config_boolean(sample_data, "d")


def test_config_dict_returns_dict():
    assert config_dict(sample_data, ["b"]) == sample_data["b"]


def test_config_dict_strict_returns_dict():
    assert config_dict_strict(sample_data, ["b"], ["x"]) == sample_data["b"]


def test_config_dict_strict_raises_if_keys_missing():
    with pytest.raises(ValueError, match="Expected keys x, y for b"):
        config_dict_strict(sample_data, ["b"], ["x", "y"])


def test_config_dict_strict_raises_if_not_strings():
    dat = {"a": {"b": {"c": 1}}}
    with pytest.raises(ValueError, match="Expected a string for a:b:c"):
        config_dict_strict(dat, ["a", "b"], "c")


def test_config_dict_strict_returns_null_if_optional():
    dat = {"a": {"b": {"c": 1}}}
    assert config_dict_strict(dat, ["x"], "c", True) is None


def test_config_enum_returns_string():
    assert config_enum(sample_data, ["b", "x"], ["value1", "value2"]) == \
        "value2"


def test_config_enum_raises_if_invalid():
    with pytest.raises(ValueError,
                       match=r"Expected one of \[enum1, enum2\] for b:x"):
        config_enum(sample_data, ["b", "x"], ["enum1", "enum2"])


def test_config_image_reference():
    data = {"foo": {
        "repo": "a", "name": "b", "tag": "c", "other": "d", "num": 1}}
    assert str(config_image_reference(data, "foo")) == "a/b:c"
    assert str(config_image_reference(data, ["foo"], "other")) == "a/d:c"
    with pytest.raises(KeyError):
        config_image_reference(data, ["foo"], "missing")
    with pytest.raises(ValueError):
        config_image_reference(data, ["foo"], "num")


def test_read_yaml():
    with tempfile.NamedTemporaryFile() as f:
        f.write(b"a: 1\n")
        f.seek(0)
        dat = read_yaml(f.name)
        assert dat == {"a": 1}


def test_config_vault():
    data = {
        "vault": {
            "addr": "https://example.com/vault",
            "auth": {
                "method": "github",
                "args": {
                    "token": "mytoken"
                }
            }
        }
    }
    value = config_vault(data, ["vault"])
    assert type(value) == vault.vault_config
    assert value.url == "https://example.com/vault"
    assert value.auth_method == "github"
    assert value.auth_args == {"token": "mytoken"}
