import base64
import io
import pytest
import tempfile

from contextlib import redirect_stdout

from constellation.docker_util import *


def test_exec_returns_output():
    cl = docker.client.from_env()
    container = cl.containers.run("alpine", ["sleep", "10"],
                                  detach=True, auto_remove=True)
    res = exec_safely(container, "ls")
    container.kill()
    assert res.exit_code == 0


def test_exec_safely_throws_on_failure():
    cl = docker.client.from_env()
    container = cl.containers.run("alpine", ["sleep", "10"],
                                  detach=True, auto_remove=True)
    with pytest.raises(Exception):
        exec_safely(container, "missing_command")
    container.kill()


def test_remove_network_removes_network():
    cl = docker.client.from_env()
    name = "constellation_test_nw"

    cl.networks.create(name)

    f = io.StringIO()
    with redirect_stdout(f):
        remove_network(name)

    assert f.getvalue() == "Removing network '{}'\n".format(name)
    assert name not in [x.name for x in cl.networks.list()]


def test_remove_network_is_silent_for_missing_networks():
    cl = docker.client.from_env()
    name = "constellation_test_nw"
    f = io.StringIO()
    with redirect_stdout(f):
        remove_network(name)

    assert f.getvalue() == ""
    assert name not in [x.name for x in cl.networks.list()]


def test_remove_volume_removes_volume():
    cl = docker.client.from_env()
    name = "constellation_test_vol"

    cl.volumes.create(name)

    f = io.StringIO()
    with redirect_stdout(f):
        remove_volume(name)

    assert f.getvalue() == "Removing volume '{}'\n".format(name)
    assert name not in [x.name for x in cl.volumes.list()]


def test_remove_volume_is_silent_for_missing_volumes():
    cl = docker.client.from_env()
    name = "constellation_test_vol"
    f = io.StringIO()
    with redirect_stdout(f):
        remove_volume(name)

    assert f.getvalue() == ""
    assert name not in [x.name for x in cl.volumes.list()]


def test_string_into_container():
    cl = docker.client.from_env()
    container = cl.containers.run("alpine", ["sleep", "20"],
                                  detach=True, auto_remove=True)
    text = "a\nb\nc\n"
    string_into_container(text, container, "/test")
    out = container.exec_run(["cat", "/test"])
    assert out.exit_code == 0
    assert out.output.decode("UTF-8") == text

    assert string_from_container(container, "/test") == text
    container.kill()


def test_file_into_container():
    cl = docker.client.from_env()
    container = cl.containers.run("alpine", ["sleep", "20"],
                                  detach=True, auto_remove=True)
    # part of a PNG - doesn't really matter, so long as it's binary:
    content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
    with tempfile.NamedTemporaryFile() as f:
        f.write(content)
        f.seek(0)
        file_into_container(f.name, container, ".", "test_name.png")

    out = container.exec_run(["cat", "test_name.png"])
    assert out.exit_code == 0
    assert out.output == content
    container.kill()


def test_container_wait_running_detects_start_failure():
    cl = docker.client.from_env()
    container = cl.containers.create("alpine")
    with pytest.raises(Exception, match=r"is not running \(created\)"):
        container_wait_running(container, 0.1, 0.1)


def test_container_wait_running_detects_slow_failure():
    cl = docker.client.from_env()
    with pytest.raises(Exception, match="was running but is now exited"):
        container = cl.containers.run("alpine", ["sleep", "1"],
                                      detach=True)
        container_wait_running(container, 0.1, 1.2)


def test_container_wait_running_returns_container():
    cl = docker.client.from_env()
    container = cl.containers.run("alpine", ["sleep", "100"], detach=True)
    res = container_wait_running(container, 0.1, 1.2)
    assert res == container
    container.kill()
    container.remove()


def test_return_logs_and_remove_returns_stdout():
    result = return_logs_and_remove("alpine", ["echo", "1234"])
    assert "1234" in result


def test_return_logs_and_remove_returns_stderr():
    result = return_logs_and_remove("alpine", ["sh", "./nonsense"])
    assert "can't open './nonsense'" in result


def test_ensure_network_creates_network():
    cl = docker.client.from_env()
    nm = "constellation_example_nw"
    assert nm not in [x.name for x in cl.networks.list()]
    f = io.StringIO()
    with redirect_stdout(f):
        ensure_network(nm)

    msg = "Creating docker network 'constellation_example_nw'\n"
    assert f.getvalue() == msg
    assert nm in [x.name for x in cl.networks.list()]
    assert network_exists(nm)

    f = io.StringIO()
    with redirect_stdout(f):
        ensure_network(nm)
    assert f.getvalue() == ""
    assert nm in [x.name for x in cl.networks.list()]

    cl.networks.get(nm).remove()


def test_ensure_volume_creates_volume():
    cl = docker.client.from_env()
    nm = "constellation_example_vol"
    assert nm not in [x.name for x in cl.volumes.list()]
    f = io.StringIO()
    with redirect_stdout(f):
        ensure_volume(nm)

    msg = "Creating docker volume 'constellation_example_vol'\n"
    assert f.getvalue() == msg
    assert nm in [x.name for x in cl.volumes.list()]
    assert volume_exists(nm)

    f = io.StringIO()
    with redirect_stdout(f):
        ensure_volume(nm)
    assert f.getvalue() == ""
    assert nm in [x.name for x in cl.volumes.list()]

    cl.volumes.get(nm).remove()


def test_pull_container():
    client = docker.client.from_env()
    # NOTE: you have to be careful here because the default python
    # docker client behaviour when pulling an image without specifying
    # a tag name is to pull *all* images, which is surprising.
    name = "hello-world:latest"
    try:
        client.images.remove(name)
    except docker.errors.NotFound:
        pass

    assert not image_exists(name)

    f = io.StringIO()
    with redirect_stdout(f):
        image_pull("example", name)

    assert image_exists(name)
    assert "Pulling docker image example (hello-world:latest)" in f.getvalue()
    assert "updated" in f.getvalue()

    f = io.StringIO()
    with redirect_stdout(f):
        image_pull("example", name)

    assert image_exists(name)
    assert "Pulling docker image example (hello-world:latest)" in f.getvalue()
    assert "unchanged" in f.getvalue()


def test_ignoring_missing_does_not_raise():
    try:
        with ignoring_missing():
            docker.client.from_env().containers.get("nosuchcontainer")
    except Exception:
        pytest.fail("Unexpected error")
