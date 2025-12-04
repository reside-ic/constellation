import random
import string
from dataclasses import dataclass


@dataclass
class ImageReference:
    repo: str
    name: str
    tag: str

    def __str__(self):
        return f"{self.repo}/{self.name}:{self.tag}"


@dataclass
class BuildSpec:
    # Path to the directory containing the Dockerfile
    path: str


def tabulate(x):
    ret = {}
    for el in x:
        if el in ret.keys():
            ret[el] += 1
        else:
            ret[el] = 1
    return ret


def rand_str(n, prefix=""):
    s = "".join(random.choice(string.ascii_lowercase) for i in range(n))
    return prefix + s
