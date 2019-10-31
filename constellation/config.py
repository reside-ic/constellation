import copy
import tempfile
import yaml

import constellation.vault as vault
from constellation.util import ImageReference


def read_yaml(filename):
    with open(filename, "r") as f:
        dat = yaml.load(f, Loader=yaml.SafeLoader)
    return dat


def config_build(path, data, extra=None, options=None):
    data = copy.deepcopy(data)
    if extra:
        data_extra = read_yaml("{}/{}.yml".format(path, extra))
        config_check_additional(data_extra)
        combine(data, data_extra)
    if options:
        if type(options) == list:
            options = collapse(options)
        config_check_additional(options)
        combine(data, options)
    return data


# Utility function for centralising control over pulling information
# out of the configuration.
def config_value(data, path, data_type, is_optional, default=None):
    if type(path) is str:
        path = [path]
    for i, p in enumerate(path):
        try:
            data = data[p]
            if data is None:
                raise KeyError()
        except KeyError as e:
            if is_optional:
                return default
            e.args = (":".join(path[:(i + 1)]),)
            raise e

    expected = {"string": str,
                "integer": int,
                "boolean": bool,
                "dict": dict}
    if type(data) is not expected[data_type]:
        raise ValueError("Expected {} for {}".format(
            data_type, ":".join(path)))
    return data


# TODO: This can be made better with respect to optional values (e.g.,
# if url is present other keys are required).
def config_vault(data, path):
    url = config_string(data, path + ["addr"], True)
    auth_method = config_string(data, path + ["auth", "method"], True)
    auth_args = config_dict(data, path + ["auth", "args"], True)
    return vault.vault_config(url, auth_method, auth_args)


def config_string(data, path, is_optional=False, default=None):
    return config_value(data, path, "string", is_optional, default)


def config_integer(data, path, is_optional=False, default=None):
    return config_value(data, path, "integer", is_optional, default)


def config_boolean(data, path, is_optional=False, default=None):
    return config_value(data, path, "boolean", is_optional, default)


def config_dict(data, path, is_optional=False, default=None):
    return config_value(data, path, "dict", is_optional, default)


def config_dict_strict(data, path, keys, is_optional=False, default=None):
    d = config_dict(data, path, is_optional)
    if not d:
        return default
    if set(keys) != set(d.keys()):
        raise ValueError("Expected keys {} for {}".format(
            ", ".join(keys), ":".join(path)))
    for k, v in d.items():
        if type(v) is not str:
            raise ValueError("Expected a string for {}".format(
                ":".join(path + [k])))
    return d


def config_enum(data, path, values, is_optional=False, default=None):
    value = config_string(data, path, is_optional, default)
    if value not in values:
        raise ValueError("Expected one of [{}] for {}".format(
            ", ".join(values), ":".join(path)))
    return value


def config_image_reference(dat, path, name="name"):
    if type(path) is str:
        path = [path]
    repo = config_string(dat, path + ["repo"])
    name = config_string(dat, path + [name])
    tag = config_string(dat, path + ["tag"])
    return ImageReference(repo, name, tag)


def config_check_additional(options):
    if "container_prefix" in options:
        raise Exception("'container_prefix' may not be modified")


def combine(base, extra):
    """Combine exactly two dictionaries recursively, modifying the first
argument in place with the contets of the second"""
    for k, v in extra.items():
        if k in base and type(base[k]) is dict and v is not None:
            combine(base[k], v)
        else:
            base[k] = v


def collapse(options):
    """Combine a list of dictionaries recursively, combining from left to
right so that later dictionaries override values in earlier ones"""
    ret = {}
    for o in options:
        combine(ret, o)
    return ret
