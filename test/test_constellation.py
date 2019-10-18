import io
import pytest
import random
import string

from contextlib import redirect_stdout

from constellation.constellation import *


def rand_str(n=10, prefix="constellation_"):
    s = "".join(random.choice(string.ascii_lowercase) for i in range(n))
    return prefix + s


def test_container_ports_creates_ports_dictionary():
    assert container_ports([]) is None
    assert container_ports(None) is None
    assert container_ports([80]) == {"80/tcp": 80}
    assert container_ports([80, 443]) == {"80/tcp": 80, "443/tcp": 443}


def test_network():
    name = rand_str()
    nw = ConstellationNetwork(name)
    assert not nw.exists()
    nw.create()
    assert nw.exists()
    assert docker_util.network_exists(name)
    nw.remove()
    assert not nw.exists()


def test_volume():
    name = rand_str()
    role = "role"
    vol = ConstellationVolume(role, name)
    assert not vol.exists()
    vol.create()
    assert vol.exists()
    assert docker_util.volume_exists(name)
    vol.remove()
    assert not vol.exists()


def test_volume_collection():
    role1 = "role1"
    role2 = "role2"
    v1 = ConstellationVolume(role1, rand_str())
    v2 = ConstellationVolume(role2, rand_str())
    obj = ConstellationVolumeCollection([v1, v2])
    assert obj.get(role1) == v1.name
    assert obj.get(role2) == v2.name
    obj.create()
    assert v1.exists()
    assert v2.exists()
    obj.remove()
    assert not v1.exists()
    assert not v2.exists()


# This one needs the volume collection to test
def test_mount_with_no_args():
    v1 = ConstellationVolume("role1", rand_str())
    v2 = ConstellationVolume("role2", rand_str())
    vols = ConstellationVolumeCollection([v1, v2])
    m = ConstellationMount("role1", "path")
    assert m.name == "role1"
    assert m.path == "path"
    assert m.kwargs == {}
    assert m.to_mount(vols) == docker.types.Mount("path", v1.name)


def test_mount_with_args():
    v1 = ConstellationVolume("role1", rand_str())
    v2 = ConstellationVolume("role2", rand_str())
    vols = ConstellationVolumeCollection([v1, v2])
    m = ConstellationMount("role1", "path", read_only=True)
    assert m.name == "role1"
    assert m.path == "path"
    assert m.kwargs == {"read_only": True}
    assert m.to_mount(vols) == docker.types.Mount("path", v1.name,
                                                  read_only=True)


def test_container_simple():
    nm = rand_str(prefix="")
    x = ConstellationContainer(nm, "library/redis:5.0")
    assert x.name_external("prefix") == "prefix_{}".format(nm)
    assert not x.exists("prefix")
    assert x.get("prefix") is None
    f = io.StringIO()
    with redirect_stdout(f):
        x.stop("prefix")
        x.kill("prefix")
        x.remove("prefix")
    assert f.getvalue() == ""


def test_container_start():
    nm = rand_str(prefix="")
    x = ConstellationContainer(nm, "library/redis:5.0")
    nw = ConstellationNetwork(rand_str())
    nw.create()
    x.start("prefix", nw, None)
    assert x.exists("prefix")
    cl = docker.client.from_env()
    assert cl.networks.get(nw.name).containers == [x.get("prefix")]
    x.stop("prefix")
    x.remove("prefix")
    assert not x.exists("prefix")
