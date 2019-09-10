import tempfile
import yaml

import constellation.vault as vault


def read_yaml(filename):
    with open(filename, "r") as f:
        dat = yaml.load(f, Loader=yaml.SafeLoader)
    return dat


# Utility function for centralising control over pulling information
# out of the configuration.
def config_value(data, path, data_type, is_optional):
    if type(path) is str:
        path = [path]
    for i, p in enumerate(path):
        try:
            data = data[p]
            if data is None:
                raise KeyError()
        except KeyError as e:
            if is_optional:
                return None
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


# TODO: once we have support for easily overriding parts of
# configuration, this can be made better with respect to optional
# values (e.g., if url is present other keys are required).
def config_vault(data, path):
    url = config_string(data, path + ["addr"], True)
    auth_method = config_string(data, path + ["auth", "method"], True)
    auth_args = config_dict(data, path + ["auth", "args"], True)
    return vault.vault_config(url, auth_method, auth_args)


def config_string(data, path, is_optional=False):
    return config_value(data, path, "string", is_optional)


def config_integer(data, path, is_optional=False):
    return config_value(data, path, "integer", is_optional)


def config_boolean(data, path, is_optional=False):
    return config_value(data, path, "boolean", is_optional)


def config_dict(data, path, is_optional=False):
    return config_value(data, path, "dict", is_optional)


def config_dict_strict(data, path, keys, is_optional=False):
    d = config_dict(data, path, is_optional)
    if not d:
        return None
    if set(keys) != set(d.keys()):
        raise ValueError("Expected keys {} for {}".format(
            ", ".join(keys), ":".join(path)))
    for k, v in d.items():
        if type(v) is not str:
            raise ValueError("Expected a string for {}".format(
                ":".join(path + [k])))
    return d


def config_enum(data, path, values, is_optional=False):
    value = config_string(data, path, is_optional)
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
    return DockerImageReference(repo, name, tag)


class DockerImageReference:
    def __init__(self, repo, name, tag):
        self.repo = repo
        self.name = name
        self.tag = tag

    def __str__(self):
        return "{}/{}:{}".format(self.repo, self.name, self.tag)
