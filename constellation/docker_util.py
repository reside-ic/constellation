import math
import os
import tarfile
import tempfile
import time

import docker


def ensure_network(name):
    client = docker.client.from_env()
    try:
        client.networks.get(name)
    except docker.errors.NotFound:
        print("Creating docker network '{}'".format(name))
        client.networks.create(name)


def ensure_volume(name):
    client = docker.client.from_env()
    try:
        client.volumes.get(name)
    except docker.errors.NotFound:
        print("Creating docker volume '{}'".format(name))
        client.volumes.create(name)


def exec_safely(container, args):
    ans = container.exec_run(args)
    if ans[0] != 0:
        print(ans[1].decode("UTF-8"))
        raise Exception("Error running command (see above for log)")
    return ans


def return_logs_and_remove(image, args=None, mounts=None):
    client = docker.client.from_env()
    try:
        result = client.containers.run(image,
                                       args,
                                       mounts=mounts,
                                       stderr=True,
                                       remove=True)
    except docker.errors.ContainerError as e:
        result = e.stderr
    return result.decode("UTF-8")


def remove_network(name):
    client = docker.client.from_env()
    try:
        nw = client.networks.get(name)
    except docker.errors.NotFound:
        return
    print("Removing network '{}'".format(name))
    nw.remove()


def remove_volume(name):
    client = docker.client.from_env()
    try:
        v = client.volumes.get(name)
    except docker.errors.NotFound:
        return
    print("Removing volume '{}'".format(name))
    v.remove(name)


def container_exists(name):
    return docker_exists("containers", name)


def network_exists(name):
    return docker_exists("networks", name)


def volume_exists(name):
    return docker_exists("volumes", name)


def image_exists(name):
    return docker_exists("images", name)


def docker_exists(collection, name):
    client = docker.client.from_env()
    try:
        client.__getattribute__(collection).get(name)
        return True
    except docker.errors.NotFound:
        return False


# https://medium.com/@nagarwal/lifecycle-of-docker-container-d2da9f85959
def container_wait_running(container, poll=0.1, timeout=1):
    for i in range(math.ceil(timeout / poll)):
        if container.status != "created":
            break
        time.sleep(poll)
        container.reload()
    if container.status != "running":
        raise Exception("container '{}' ({}) is not running ({})".format(
            container.name, container.id[:8], container.status))
    time.sleep(timeout)
    container.reload()
    if container.status != "running":
        raise Exception("container '{}' ({}) was running but is now {}".format(
            container.name, container.id[:8], container.status))
    return container


def simple_tar(path, name):
    f = tempfile.NamedTemporaryFile()
    t = tarfile.open(mode="w", fileobj=f)
    abs_path = os.path.abspath(path)
    t.add(abs_path, arcname=name, recursive=False)
    t.close()
    f.seek(0)
    return f


def simple_tar_string(text, name):
    try:
        fd, tmp = tempfile.mkstemp(text=True)
        with os.fdopen(fd, "w") as f:
            f.write(text)
        return simple_tar(tmp, name)
    finally:
        os.remove(tmp)


# The python docker client does not provide nice 'docker cp' wrappers
# (https://github.com/docker/docker-py/issues/1771) - so we have to
# roll our own.  These are a real pain to do "properly".  For example
# see
# https://github.com/richfitz/stevedore/blob/845587/R/docker_client_support.R#L943-L1020
#
# So this function assumes that the destination directory exists and
# dumps out text into a file in the container
def string_into_container(txt, container, path):
    with simple_tar_string(txt, os.path.basename(path)) as tar:
        container.put_archive(os.path.dirname(path), tar)


def file_into_container(local_path, container, destination_path, name):
    tar = simple_tar(local_path, name)
    container.put_archive(destination_path, tar)


def string_from_container(container, path):
    stream, status = container.get_archive(path)
    try:
        fd, tmp = tempfile.mkstemp(text=False)
        with os.fdopen(fd, "wb") as f:
            for d in stream:
                f.write(d)
        with open(tmp, "rb") as f:
            t = tarfile.open(mode="r", fileobj=f)
            p = t.extractfile(os.path.basename(path))
            txt = p.readlines()
            return "".join([x.decode("utf8") for x in txt])
    finally:
        os.remove(tmp)


# NOTE: you have to be careful here because the default python docker
# client behaviour when pulling an image without specifying a tag name
# is to pull *all* images, which is surprising.
# https://docker-py.readthedocs.io/en/stable/images.html
def image_pull(name, ref):
    client = docker.client.from_env()
    print("Pulling docker image {} ({})".format(name, ref))
    try:
        prev = client.images.get(ref).short_id
    except docker.errors.NotFound:
        prev = None
    curr = client.images.pull(ref).short_id
    status = "unchanged" if prev == curr else "updated"
    print("    `-> {} ({})".format(curr, status))


class ignoring_missing:
    def __init__(self):
        pass

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        # For some reason, in create_api_error_from_http_exception,
        # docker-py classes all 404 errors as NotFound *except* for
        # images. It's not totally obvious how we can use the subclass
        # information here either.
        if type is docker.errors.NotFound or docker.errors.ImageNotFound:
            return True
