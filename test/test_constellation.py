import io
import pytest
import random
import string
import vault_dev

from contextlib import redirect_stdout

from constellation.constellation import *
from constellation.util import ImageReference


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
    name1 = rand_str()
    name2 = rand_str()
    vols = ConstellationVolumeCollection({role1: name1, role2: name2})

    assert vols.get(role1) == name1
    assert vols.get(role2) == name2
    with pytest.raises(Exception, match="Mount with role 'foo' not defined"):
        vols.get("foo")
    vols.create()
    assert docker_util.volume_exists(name1)
    assert docker_util.volume_exists(name2)
    vols.remove()
    assert not docker_util.volume_exists(name1)
    assert not docker_util.volume_exists(name2)


def test_empty_volume_collection():
    vols = ConstellationVolumeCollection({})
    assert vols.collection == []
    try:
        vols.create()
        vols.remove()
    except Exception:
        pytest.fail("Unexpected error")


# This one needs the volume collection to test
def test_mount_with_no_args():
    role1 = "role1"
    role2 = "role2"
    name1 = rand_str()
    name2 = rand_str()
    vols = ConstellationVolumeCollection({role1: name1, role2: name2})
    m = ConstellationMount(role1, "path")
    assert m.name == "role1"
    assert m.path == "path"
    assert m.kwargs == {}
    assert m.to_mount(vols) == docker.types.Mount("path", name1)


def test_mount_with_args():
    role1 = "role1"
    role2 = "role2"
    name1 = rand_str()
    name2 = rand_str()
    vols = ConstellationVolumeCollection({role1: name1, role2: name2})

    m = ConstellationMount("role1", "path", read_only=True)
    assert m.name == "role1"
    assert m.path == "path"
    assert m.kwargs == {"read_only": True}
    assert m.to_mount(vols) == docker.types.Mount("path", name1,
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
        x.stop("prefix", True)
        x.remove("prefix")
    assert f.getvalue() == ""


def test_container_start_stop_remove():
    nm = rand_str(prefix="")
    x = ConstellationContainer(nm, "library/redis:5.0")
    nw = ConstellationNetwork(rand_str())
    try:
        nw.create()
        x.start("prefix", nw, None)
        assert x.exists("prefix")
        cl = docker.client.from_env()
        assert cl.networks.get(nw.name).containers == [x.get("prefix")]
        x.stop("prefix")
        x.remove("prefix")
        assert not x.exists("prefix")
    finally:
        nw.remove()


def test_container_start_configure():
    def configure(container, data):
        docker_util.string_into_container("hello\n", container, "/hello")

    try:
        nm = rand_str(prefix="")
        x = ConstellationContainer(nm, "library/redis:5.0",
                                   configure=configure)
        nw = ConstellationNetwork(rand_str())
        nw.create()
        x.start("prefix", nw, None)
        s = docker_util.string_from_container(x.get("prefix"), "/hello")
        assert s == "hello\n"
    finally:
        x.stop("prefix", True)
        nw.remove()


def test_container_pull():
    ref = "library/hello-world:latest"
    x = ConstellationContainer("hello", ref)
    with docker_util.ignoring_missing():
        docker.client.from_env().images.remove(ref)
    x.pull_image()
    assert docker_util.image_exists(ref)


def test_container_collection():
    ref = "library/redis:5.0"
    prefix = rand_str()
    nw = ConstellationNetwork(rand_str())
    nw.create()
    x = ConstellationContainer("server", ref)
    y = ConstellationContainer("client", ref)
    obj = ConstellationContainerCollection([x, y])

    assert obj.get("client", prefix) is None
    with pytest.raises(Exception, match="Container 'foo' not defined"):
        obj.get("foo", prefix)

    assert obj.exists(prefix) == [False, False]
    obj.pull_images()
    obj.start(prefix, nw, [])

    cl = obj.get("client", prefix)
    assert cl.name == "{}_client".format(prefix)
    assert obj.exists(prefix) == [True, True]
    obj.stop(prefix)
    obj.remove(prefix)
    nw.remove()


def test_constellation():
    """Bring up a simple constellation and verify that it works"""
    name = "mything"
    prefix = rand_str()
    network = "thenw"
    volumes = {"data": "mydata"}
    ref_server = ImageReference("library", "nginx", "latest")
    ref_client = ImageReference("library", "alpine", "latest")
    arg_client = ["sleep", "1000"]

    def cfg_client(container, data):
        res = container.exec_run(["apk", "add", "--no-cache", "curl"])
        assert res.exit_code == 0

    server = ConstellationContainer("server", ref_server)
    client = ConstellationContainer("client", ref_client, arg_client,
                                    configure=cfg_client)

    obj = Constellation(name, prefix, [server, client], network, volumes)

    f = io.StringIO()
    with redirect_stdout(f):
        obj.status()

    p = f.getvalue()

    assert "Network:\n    - thenw: missing" in p
    assert "Volumes:\n    - data (mydata): missing" in p
    assert "Containers:\n    - server ({}_server): missing".format(prefix) in p

    obj.start(True)

    f = io.StringIO()
    with redirect_stdout(f):
        obj.status()

    p = f.getvalue()

    assert "Network:\n    - thenw: created" in p
    assert "Volumes:\n    - data (mydata): created" in p
    assert "Containers:\n    - server ({}_server): running".format(prefix) in p

    x = obj.containers.get("client", prefix)
    response = docker_util.exec_safely(x, ["curl", "http://server"])
    assert "Welcome to nginx" in response.output.decode("UTF-8")

    with pytest.raises(Exception, match="Some containers exist"):
        obj.start()

    obj.destroy()


def test_constellation_fetches_secrets_on_startup():
    name = "mything"
    prefix = rand_str()
    network = "thenw"
    volumes = {"data": "mydata"}
    ref_server = ImageReference("library", "nginx", "latest")
    ref_client = ImageReference("library", "alpine", "latest")
    arg_client = ["sleep", "1000"]
    data = {"string": "VAULT:secret/foo:value"}

    with vault_dev.server() as s:
        vault_client = s.client()
        vault_url = vault_client.url
        secret = rand_str()
        vault_client.write("secret/foo", value=secret)

        def cfg_server(container, data):
            res = docker_util.string_into_container(
                data["string"], container, "/config")

        def cfg_client(container, data):
            res = container.exec_run(["apk", "add", "--no-cache", "curl"])
            assert res.exit_code == 0

        vault_config = vault.vault_config(vault_client.url, "token",
                                          {"token": s.token})

        server = ConstellationContainer("server", ref_server,
                                        configure=cfg_server)
        client = ConstellationContainer("client", ref_client, arg_client,
                                        configure=cfg_client)

        obj = Constellation(name, prefix, [server, client], network, volumes,
                            data=data, vault_config=vault_config)

        obj.start()
        x = obj.containers.get("server", prefix)
        res = docker_util.string_from_container(x, "/config")
        assert res == secret
        obj.destroy()
