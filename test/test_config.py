import pytest

from constellation.config import *

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


def test_combine():
    def do_combine(a, b):
        """lets us use combine with unnamed data"""
        combine(a, b)
        return a

    assert do_combine({"a": 1}, {"b": 2}) == \
        {"a": 1, "b": 2}
    assert do_combine({"a": {"x": 1}, "b": 2}, {"a": {"x": 3}}) == \
        {"a": {"x": 3}, "b": 2}
    assert do_combine({"a": {"x": 1, "y": 4}, "b": 2}, {"a": {"x": 3}}) == \
        {"a": {"x": 3, "y": 4}, "b": 2}
    assert do_combine({"a": None, "b": 2}, {"a": {"x": 3}}) == \
        {"a": {"x": 3}, "b": 2}


def test_combine_can_replace_dict():
    base = {"a": {"c": {"d": "x"}}, "b": "y"}
    options = {"a": {"c": None}}
    combine(base, options)
    assert base["a"]["c"] is None


def test_collapse():
    base = {"a": 1, "b": 2}
    assert collapse([]) == {}
    assert collapse([base]) == base
    assert collapse([base, base]) == base
    assert collapse([base, {"a": 2}]) == {"a": 2, "b": 2}
    assert collapse([base, {"a": 2}, {"a": 3}]) == {"a": 3, "b": 2}


def test_config_build_works():
    base = "a: 1\nb: 2\nc: 3\n"
    extra = "a: 2\nb: 4"
    options = {"a": 3, "c": 9, "x": "y"}
    options2 = [options, {"x": "z"}]
    with tempfile.TemporaryDirectory() as path:
        path_base = path + "/base.yml"
        path_extra = path + "/options.yml"
        write_file(base, path_base)
        write_file(extra, path_extra)
        data = read_yaml(path_base)
        assert config_build(path, data) == data
        assert config_build(path, data, "options") == {"a": 2, "b": 4, "c": 3}
        assert config_build(path, data, None, options) == \
            {"a": 3, "b": 2, "c": 9, "x": "y"}
        assert config_build(path, data, None, options2) == \
            {"a": 3, "b": 2, "c": 9, "x": "z"}


def test_config_build_prevents_changing_container_prefix():
    base = "container_prefix: a\nb: 2\nc: 3\n"
    extra = "container_prefix: b\na: 2"
    options = {"container_prefix": "c", "a": 3}
    with tempfile.TemporaryDirectory() as path:
        path_base = path + "/base.yml"
        path_extra = path + "/options.yml"
        write_file(base, path_base)
        write_file(extra, path_extra)
        data = read_yaml(path_base)
        msg = "'container_prefix' may not be modified"
        with pytest.raises(Exception, match=msg):
            config_build(path, data, "options")
        with pytest.raises(Exception, match=msg):
            config_build(path, data, None, options)


def write_file(contents, path):
    with open(path, "w") as f:
        f.write(contents)
