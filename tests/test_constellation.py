import io
from contextlib import redirect_stdout

import docker
import pytest
import vault_dev

from constellation.constellation import (
    Constellation,
    ConstellationBindMount,
    ConstellationContainer,
    ConstellationContainerCollection,
    ConstellationNetwork,
    ConstellationService,
    ConstellationVolume,
    ConstellationVolumeCollection,
    ConstellationVolumeMount,
    container_ports,
    docker_util,
    port_config,
    vault,
)
from constellation.util import ImageReference, rand_str


def drop_image(ref):
    with docker_util.ignoring_missing():
        docker.client.from_env().images.remove(ref)


def constellation_rand_str(n=10, prefix="constellation-"):
    return rand_str(n, prefix)


def test_ports_create_port_config_and_container_ports():
    assert port_config([]) is None
    assert port_config(None) is None
    assert port_config([80]) == {80: 80}
    assert port_config([80, 443]) == {80: 80, 443: 443}
    assert port_config([(5432, 15432)]) == {5432: 15432}
    assert port_config([(5432, 15432), 1]) == {5432: 15432, 1: 1}

    assert container_ports(None) is None
    assert container_ports({80: 80}) == [80]
    assert container_ports({80: 80, 443: 443}) == [80, 443]
    assert container_ports({1: 2, 3: 4, 5: 5}) == [1, 3, 5]


def test_network():
    name = constellation_rand_str()
    nw = ConstellationNetwork(name)
    assert not nw.exists()
    nw.create()
    assert nw.exists()
    assert docker_util.network_exists(name)
    nw.remove()
    assert not nw.exists()


def test_volume():
    name = constellation_rand_str()
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
    name1 = constellation_rand_str()
    name2 = constellation_rand_str()
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


def test_volume_mount_with_relative_paths():
    with pytest.raises(
        ValueError, match=r"Path 'target_path' must be an absolute path."
    ):
        ConstellationVolumeMount("role1", "target_path")


# This one needs the volume collection to test
def test_volume_mount_with_no_args():
    role1 = "role1"
    role2 = "role2"
    name1 = constellation_rand_str()
    name2 = constellation_rand_str()
    vols = ConstellationVolumeCollection({role1: name1, role2: name2})

    absolute_target_path = "/target_path"
    m = ConstellationVolumeMount(role1, absolute_target_path)
    assert m.name == "role1"
    assert m.target == absolute_target_path
    assert m.kwargs == {"type": "volume"}
    assert m.to_mount(vols) == docker.types.Mount(
        absolute_target_path, name1, type="volume"
    )


def test_volume_mount_with_args():
    role1 = "role1"
    role2 = "role2"
    name1 = constellation_rand_str()
    name2 = constellation_rand_str()
    vols = ConstellationVolumeCollection({role1: name1, role2: name2})

    absolute_target_path = "/target_path"
    m = ConstellationVolumeMount("role1", absolute_target_path, read_only=True)
    assert m.name == "role1"
    assert m.target == absolute_target_path
    assert m.kwargs == {"type": "volume", "read_only": True}
    assert m.to_mount(vols) == docker.types.Mount(
        absolute_target_path, name1, type="volume", read_only=True
    )


def test_bind_mount_with_relative_paths():
    with pytest.raises(
        ValueError, match=r"Path 'target_path' must be an absolute path."
    ):
        ConstellationBindMount("/source_path", "target_path")
    with pytest.raises(
        ValueError, match=r"Path 'source_path' must be an absolute path."
    ):
        ConstellationBindMount("source_path", "/target_path")


def test_bind_mount_with_no_args():
    role1 = "role1"
    role2 = "role2"
    name1 = constellation_rand_str()
    name2 = constellation_rand_str()
    # Creat volume collection so that we can test the interface of to_mount
    vols = ConstellationVolumeCollection({role1: name1, role2: name2})

    m = ConstellationBindMount("/source_path", "/target_path")
    assert m.source == "/source_path"
    assert m.target == "/target_path"
    assert m.kwargs == {"type": "bind"}
    assert m.to_mount(vols) == docker.types.Mount(
        "/target_path", "/source_path", type="bind"
    )


def test_bind_mount_with_args():
    role1 = "role1"
    role2 = "role2"
    name1 = constellation_rand_str()
    name2 = constellation_rand_str()
    vols = ConstellationVolumeCollection({role1: name1, role2: name2})

    m = ConstellationBindMount("/source_path", "/target_path", read_only=True)
    assert m.source == "/source_path"
    assert m.target == "/target_path"
    assert m.kwargs == {"type": "bind", "read_only": True}
    assert m.to_mount(vols) == docker.types.Mount(
        "/target_path", "/source_path", type="bind", read_only=True
    )


def test_container_simple():
    nm = rand_str(n=10, prefix="")
    cl = docker.client.from_env()
    cl.images.pull("library/redis:5.0")
    x = ConstellationContainer(nm, "library/redis:5.0")
    assert x.name_external("prefix") == f"prefix-{nm}"
    assert not x.exists("prefix")
    assert x.get("prefix") is None
    f = io.StringIO()
    with redirect_stdout(f):
        x.stop("prefix")
        x.stop("prefix", True)
        x.remove("prefix")
    assert f.getvalue() == ""


def test_pull_missing_container_on_start(capsys):
    nm = rand_str(n=10, prefix="")
    ref = ImageReference("library", "redis", "5.0")

    drop_image(str(ref))

    x = ConstellationContainer(nm, ref)
    assert x.name_external("prefix") == f"prefix-{nm}"
    assert not x.exists("prefix")
    assert x.get("prefix") is None
    nw = ConstellationNetwork(constellation_rand_str())
    nw.create()

    x.start("prefix", network=nw, volumes=None)
    res = capsys.readouterr()
    assert "Pulling docker image" in res.out
    x.stop("prefix")
    x.stop("prefix", True)
    x.remove("prefix")
    nw.remove()


def test_container_start_stop_remove():
    nm = rand_str(n=10, prefix="")
    cl = docker.client.from_env()
    cl.images.pull("library/redis:5.0")
    x = ConstellationContainer(nm, "library/redis:5.0")
    nw = ConstellationNetwork(constellation_rand_str())
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
    def configure(container, _data):
        docker_util.string_into_container("hello\n", container, "/hello")

    try:
        nm = rand_str(n=10, prefix="")
        cl = docker.client.from_env()
        cl.images.pull("library/redis:5.0")
        x = ConstellationContainer(nm, "library/redis:5.0", configure=configure)
        nw = ConstellationNetwork(constellation_rand_str())
        nw.create()
        x.start("prefix", nw, None)
        s = docker_util.string_from_container(x.get("prefix"), "/hello")
        assert s == "hello\n"
    finally:
        x.stop("prefix", True)
        nw.remove()


def test_container_ports():
    try:
        nm = rand_str(n=10, prefix="")
        cl = docker.client.from_env()
        cl.images.pull("library/alpine:latest")
        x = ConstellationContainer(
            nm, "library/alpine:latest", ports=[80, (3000, 8080)]
        )
        nw = ConstellationNetwork(constellation_rand_str())
        nw.create()
        x.start("prefix", nw, None)
        container_config = cl.api.inspect_container(f"prefix-{nm}")
        port_bindings = container_config["HostConfig"]["PortBindings"]
        assert port_bindings == {
            "80/tcp": [{"HostIp": "", "HostPort": "80"}],
            "3000/tcp": [{"HostIp": "", "HostPort": "8080"}],
        }
    finally:
        x.stop("prefix", True)
        nw.remove()


def test_container_pull():
    ref = "library/hello-world:latest"
    x = ConstellationContainer("hello", ref)
    drop_image(ref)
    x.pull_image()
    assert docker_util.image_exists(ref)


def test_container_collection():
    ref = "library/redis:5.0"
    prefix = constellation_rand_str()
    nw = ConstellationNetwork(constellation_rand_str())
    nw.create()
    cl = docker.client.from_env()
    cl.images.pull("library/redis:5.0")
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
    assert cl.name == f"{prefix}-client"
    assert obj.exists(prefix) == [True, True]
    obj.stop(prefix)
    obj.remove(prefix)
    nw.remove()


def test_constellation():
    """Bring up a simple constellation and verify that it works"""
    name = "mything"
    prefix = constellation_rand_str()
    network = "thenw"
    volumes = {"data": "mydata"}
    ref_server = ImageReference("library", "nginx", "latest")
    ref_client = ImageReference("library", "alpine", "latest")
    arg_client = ["sleep", "1000"]

    def cfg_client(container, _data):
        res = container.exec_run(["apk", "add", "--no-cache", "curl"])
        assert res.exit_code == 0

    server = ConstellationContainer("server", ref_server)
    client = ConstellationContainer(
        "client", ref_client, arg_client, configure=cfg_client
    )

    obj = Constellation(name, prefix, [server, client], network, volumes)

    f = io.StringIO()
    with redirect_stdout(f):
        obj.status()

    p = f.getvalue()

    assert "Network:\n    - thenw: missing" in p
    assert "Volumes:\n    - data (mydata): missing" in p
    assert f"Containers:\n    - server ({prefix}-server): missing" in p

    obj.start(True)

    f = io.StringIO()
    with redirect_stdout(f):
        obj.status()

    p = f.getvalue()

    assert "Network:\n    - thenw: created" in p
    assert "Volumes:\n    - data (mydata): created" in p
    assert f"Containers:\n    - server ({prefix}-server): running" in p

    x = obj.containers.get("client", prefix)
    response = docker_util.exec_safely(x, ["curl", "http://server"])
    assert "Welcome to nginx" in response.output.decode("UTF-8")

    with pytest.raises(Exception, match="Some containers exist"):
        obj.start()

    obj.destroy()


def test_constellation_fetches_secrets_on_startup():
    name = "mything"
    prefix = constellation_rand_str()
    network = "thenw"
    volumes = {"data": "mydata"}
    ref_server = ImageReference("library", "nginx", "latest")
    ref_client = ImageReference("library", "alpine", "latest")
    arg_client = ["sleep", "1000"]
    data = {"string": "VAULT:secret/foo:value"}

    with vault_dev.Server() as s:
        vault_client = s.client()
        secret = constellation_rand_str()
        vault_client.write("secret/foo", value=secret)

        def cfg_server(container, data):
            docker_util.string_into_container(
                data["string"], container, "/config"
            )

        def cfg_client(container, _data):
            res = container.exec_run(["apk", "add", "--no-cache", "curl"])
            assert res.exit_code == 0

        vault_config = vault.VaultConfig(
            vault_client.url, "token", {"token": s.token}
        )

        server = ConstellationContainer(
            "server", ref_server, configure=cfg_server
        )
        client = ConstellationContainer(
            "client", ref_client, arg_client, configure=cfg_client
        )

        obj = Constellation(
            name,
            prefix,
            [server, client],
            network,
            volumes,
            data=data,
            vault_config=vault_config,
        )

        obj.start()
        x = obj.containers.get("server", prefix)
        res = docker_util.string_from_container(x, "/config")
        assert res == secret
        obj.destroy()


def test_scalable_containers():
    name = "mything"
    prefix = constellation_rand_str()
    network = "thenw"
    volumes = {"data": "mydata"}
    ref_server = ImageReference("library", "nginx", "latest")
    ref_client = ImageReference("library", "alpine", "latest")
    arg_client = ["sleep", "1000"]

    def cfg_client(container, _data):
        res = container.exec_run(["apk", "add", "--no-cache", "curl"])
        assert res.exit_code == 0

    server = ConstellationContainer("server", ref_server)
    client = ConstellationService(
        "client", ref_client, 4, args=arg_client, configure=cfg_client
    )

    obj = Constellation(name, prefix, [server, client], network, volumes)
    f = io.StringIO()
    with redirect_stdout(f):
        obj.status()

    print(f.getvalue())
    assert "client-<i>): missing" in f.getvalue()

    obj.start(pull_images=True)

    f = io.StringIO()
    with redirect_stdout(f):
        obj.status()

    assert "client-<i>): running (4)" in f.getvalue()

    containers = client.get(prefix)

    for i in range(4):
        x = containers[i]
        assert x.name.startswith(f"{prefix}-client-")
        response = docker_util.exec_safely(x, ["curl", "http://server"])
        assert "Welcome to nginx" in response.output.decode("UTF-8")

    obj.destroy()


def test_start_subset():
    name = "mything"
    prefix = constellation_rand_str()
    network = "thenw"
    volumes = {"data": "mydata"}
    ref_server = ImageReference("library", "nginx", "latest")
    ref_client = ImageReference("library", "alpine", "latest")
    arg_client = ["sleep", "1000"]

    def cfg_client(container, _data):
        res = container.exec_run(["apk", "add", "--no-cache", "curl"])
        assert res.exit_code == 0

    server = ConstellationContainer("server", ref_server)
    client = ConstellationContainer(
        "client", ref_client, arg_client, configure=cfg_client
    )

    obj = Constellation(name, prefix, [server, client], network, volumes)
    obj.start(subset=["server"])
    assert obj.network.exists()
    assert obj.volumes.collection[0].exists()
    assert obj.containers.find("server").exists(prefix)
    assert not obj.containers.find("client").exists(prefix)
    obj.start(subset=["client"])
    assert obj.containers.find("client").exists(prefix)
    obj.destroy()


def test_restart_pulls_and_replaces_containers():
    name = "mything"
    prefix = constellation_rand_str()
    network = "thenw"
    volumes = {"data": "mydata"}
    ref_server = ImageReference("library", "nginx", "latest")
    ref_client = ImageReference("library", "alpine", "latest")
    arg_client = ["sleep", "1000"]

    def cfg_client(container, _data):
        res = container.exec_run(["apk", "add", "--no-cache", "curl"])
        assert res.exit_code == 0

    server = ConstellationContainer("server", ref_server)
    client = ConstellationContainer(
        "client", ref_client, arg_client, configure=cfg_client
    )

    obj = Constellation(name, prefix, [server, client], network, volumes)
    obj.start()

    id_server = obj.containers.get("server", obj.prefix).id
    id_client = obj.containers.get("client", obj.prefix).id

    f = io.StringIO()
    with redirect_stdout(f):
        obj.restart()

    s = f.getvalue()
    assert s.startswith("Pulling docker image")
    assert "Pulling docker image server" in s
    assert "Pulling docker image client" in s
    assert s.strip().split("\n")[4:] == [
        "Stop 'server'",
        "Stop 'client'",
        "Removing 'server'",
        "Removing 'client'",
        "Starting server (library/nginx:latest)",
        "Starting client (library/alpine:latest)",
    ]

    assert obj.containers.get("server", obj.prefix).id != id_server
    assert obj.containers.get("client", obj.prefix).id != id_client

    obj.destroy()


def test_can_preconfigure_constellation_containers():
    name = "mything"
    prefix = constellation_rand_str()
    network = "thenw"
    volumes = {"data": "mydata"}
    ref_container = ImageReference("library", "alpine", "latest")
    arg_container = ["sleep", "1000"]

    def precfg_container(container, _data):
        docker_util.string_into_container(
            "test string", container, "./test.txt"
        )

    def cfg_container(container, _data):
        res = container.exec_run(["cat", "test.txt"])
        assert res.output.decode("utf-8") == "test string"

    client = ConstellationContainer(
        "client",
        ref_container,
        arg_container,
        configure=cfg_container,
        preconfigure=precfg_container,
    )

    obj = Constellation(name, prefix, [client], network, volumes)
    obj.start()
    obj.destroy()


def test_constellation_can_set_entrypoint():
    """Bring up a container with entrypoint and verify that it works"""
    name = "mything"
    ref = ImageReference("library", "alpine", "latest")

    container = ConstellationContainer(
        "alpine", ref, entrypoint="echo", args="print this"
    )

    obj = Constellation(name, "prefix", [container], "network", None)
    obj.start()

    log = container.get("prefix").logs().decode("utf-8")

    assert "print this\n" == log

    obj.destroy()


def test_constellation_can_set_working_dir():
    """Bring up a container with working dir and verify that it works"""
    name = "mything"
    ref = ImageReference("library", "alpine", "latest")

    container = ConstellationContainer("alpine", ref, entrypoint="ls")
    container_dir = ConstellationContainer(
        "alpine2", ref, entrypoint="ls", working_dir="/bin"
    )

    obj = Constellation(
        name, "prefix", [container, container_dir], "network", None
    )
    obj.start()

    log = container.get("prefix").logs().decode("utf-8")
    log_dir = container_dir.get("prefix").logs().decode("utf-8")

    assert log != log_dir
    assert "cat" in log_dir

    obj.destroy()


def test_constellation_can_set_labels():
    """Bring up a container with labels and verify that it works"""
    name = "mything"
    ref = ImageReference("library", "alpine", "latest")

    labels = {"label1": "value1", "label2": "value2"}
    container = ConstellationContainer("alpine", ref, entrypoint="ls")
    container_label = ConstellationContainer(
        "alpine2", ref, entrypoint="ls", labels=labels
    )

    obj = Constellation(
        name, "prefix", [container, container_label], "network", None
    )
    obj.start()

    assert container.get("prefix").labels == {}
    assert container_label.get("prefix").labels == labels

    obj.destroy()
