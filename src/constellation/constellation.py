from abc import abstractmethod
from pathlib import Path
from typing import Optional

import docker

from constellation import docker_util, vault
from constellation.util import rand_str, tabulate


class Constellation:
    def __init__(
        self,
        name,
        prefix,
        containers,
        network,
        volumes,
        data=None,
        vault_config=None,
        acme_buddy=None,
    ):
        self.data = data

        assert isinstance(name, str)
        self.name = name

        assert isinstance(prefix, str)
        self.prefix = prefix

        assert isinstance(network, str)
        self.network = ConstellationNetwork(network)
        self.volumes = ConstellationVolumeCollection(volumes)

        for x in containers:
            assert type(x) in [ConstellationContainer, ConstellationService]

        self.containers = ConstellationContainerCollection(containers)
        self.vault_config = vault_config
        self.acme_buddy = acme_buddy

    def status(self):
        nw_name = self.network.name
        nw_status = (
            "created" if docker_util.network_exists(nw_name) else "missing"
        )
        print(f"Constellation {self.name}")
        print("  * Network:")
        print(f"    - {nw_name}: {nw_status}")
        print("  * Volumes:")
        for v in self.volumes.collection:
            v_status = (
                "created" if docker_util.volume_exists(v.name) else "missing"
            )
            print(f"    - {v.role} ({v.name}): {v_status}")
        print("  * Containers:")
        for x in self.containers.collection:
            x_name = x.name_external(self.prefix)
            x_status = x.status(self.prefix)
            print(f"    - {x.name} ({x_name}): {x_status}")

    def start(self, pull_images=False, subset=None):
        if subset is None and any(self.containers.exists(self.prefix)):
            msg = "Some containers exist"
            raise Exception(msg)
        if self.vault_config:
            vault.resolve_secrets(self.data, self.vault_config.client())
        if pull_images:
            self.containers.pull_images()
        self.network.create()
        self.volumes.create()
        self.containers.start(
            self.prefix, self.network, self.volumes, self.data, subset
        )

    def stop(self, kill=False, remove_network=False, remove_volumes=False):
        self.containers.stop(self.prefix, kill)
        self.containers.remove(self.prefix)
        if remove_network:
            self.network.remove()
        if remove_volumes:
            self.volumes.remove()

    def restart(self, pull_images=True):
        if pull_images:
            self.containers.pull_images()
        self.stop()
        self.start()

    def destroy(self):
        self.stop(True, True, True)


class _ConstellationMount:
    """Base class for Docker mounts."""

    @abstractmethod
    def to_mount(
        self, volumes: Optional[dict] = None
    ) -> docker.types.Mount: ...

    def _assert_absolute_path(self, path):
        if not Path(path).is_absolute():
            msg = f"Path '{path}' must be an absolute path."
            raise ValueError(msg)


class ConstellationContainer:
    """For ports, to remap a port pass a tuple (port_container,
    port_host), such as:

    ports=[80, (2222, 3333)]

    which will expose port 80 (same port on both the container and
    host) and expose port 2222 in the container as 3333 on the host.
    """

    def __init__(
        self,
        name,
        image,
        args=None,
        mounts=None,
        ports=None,
        environment=None,
        configure=None,
        entrypoint=None,
        working_dir=None,
        labels=None,
        preconfigure=None,
        network="none",
    ):
        self.name = name
        self.image = image
        self.args = args
        self.mounts = mounts or []
        self.ports_config = port_config(ports)
        self.container_ports = container_ports(self.ports_config)
        self.environment = environment
        self.configure = configure
        self.entrypoint = entrypoint
        self.working_dir = working_dir
        self.labels = labels
        self.preconfigure = preconfigure
        self.network = network

    def name_external(self, prefix):
        return f"{prefix}-{self.name}"

    def pull_image(self):
        docker_util.image_pull(self.name, str(self.image))

    def exists(self, prefix):
        return docker_util.container_exists(self.name_external(prefix))

    def start(self, prefix, network, volumes, data=None):
        cl = docker.client.from_env()
        nm = self.name_external(prefix)
        print(f"Starting {self.name} ({self.image!s})")
        mounts = [x.to_mount(volumes) for x in self.mounts]

        if self.ports_config:
            # don't have to specify TCP vs UDP here because TCP is the default
            host_config = cl.api.create_host_config(
                mounts=mounts, port_bindings=self.ports_config
            )
        else:
            host_config = cl.api.create_host_config(mounts=mounts)

        endpoint_config = cl.api.create_endpoint_config(aliases=[self.name])
        networking_config = cl.api.create_networking_config(
            {f"{network.name}": endpoint_config}
        )
        docker_util.ensure_image(self.name, str(self.image))
        x_obj = cl.api.create_container(
            str(self.image),
            self.args,
            name=nm,
            detach=True,
            labels=self.labels,
            ports=self.container_ports,
            environment=self.environment,
            entrypoint=self.entrypoint,
            working_dir=self.working_dir,
            host_config=host_config,
            networking_config=networking_config,
        )
        container_id = x_obj["Id"]
        x = cl.containers.get(container_id)

        if self.preconfigure:
            self.preconfigure(x, data)

        x.start()

        if self.configure:
            self.configure(x, data)

    def get(self, prefix):
        client = docker.client.from_env()
        try:
            return client.containers.get(self.name_external(prefix))
        except docker.errors.NotFound:
            return None

    def status(self, prefix):
        container = self.get(prefix)
        return container.status if container else "missing"

    def stop(self, prefix, kill=False):
        docker_util.container_stop(self.get(prefix), kill, self.name)

    def remove(self, prefix):
        container = self.get(prefix)
        if container:
            print(f"Removing '{self.name}'")
            with docker_util.ignoring_missing():
                container.remove()


# This could be achieved by inheriting from ConstellationContainer but
# this seems more like a has-a than an is-a relationship.
class ConstellationService:
    def __init__(self, name, image, scale, **kwargs):
        self.name = name
        self.image = image
        self.scale = scale
        self.kwargs = kwargs
        self.base = ConstellationContainer(name, image, **kwargs)

    def name_external(self, prefix):
        return f"{self.base.name_external(prefix)}-<i>"

    def pull_image(self):
        self.base.pull_image()

    def exists(self, prefix):
        return bool(self.get(prefix))

    def start(self, prefix, network, volumes, data=None):
        print(f"Starting *service* {self.name}")
        for _i in range(self.scale):
            name = f"{self.name}-{rand_str(8)}"
            container = ConstellationContainer(name, self.image, **self.kwargs)
            container.start(prefix, network, volumes, data)

    def get(self, prefix, stopped=False):
        pattern = self.base.name_external(prefix) + "-"
        return docker_util.containers_matching(pattern, stopped)

    def status(self, prefix):
        status = tabulate([x.status for x in self.get(prefix)])
        if status:
            ret = ", ".join([f"{k} ({v})" for k, v in status.items()])
        else:
            ret = "missing"
        return ret

    def stop(self, prefix, kill=False):
        for x in self.get(prefix):
            docker_util.container_stop(x, kill, self.name)

    def remove(self, prefix):
        containers = self.get(prefix, True)
        if containers:
            print(f"Removing '{self.name}'")
            for x in containers:
                x.remove()


class ConstellationContainerCollection:
    def __init__(self, collection):
        self.collection = collection

    def find(self, name):
        for x in self.collection:
            if x.name == name:
                return x
        msg = f"Container '{name}' not defined"
        raise Exception(msg)

    def get(self, name, prefix):
        return self.find(name).get(prefix)

    def exists(self, prefix):
        return [x.exists(prefix) for x in self.collection]

    def _apply(self, method, *args, subset=None):
        for x in self.collection:
            if subset is None or x.name in subset:
                x.__getattribute__(method)(*args)

    def pull_images(self):
        self._apply("pull_image")

    def stop(self, prefix, kill=False):
        self._apply("stop", prefix, kill)

    def remove(self, prefix):
        self._apply("remove", prefix)

    def start(self, prefix, network, volumes, data=None, subset=None):
        self._apply("start", prefix, network, volumes, data, subset=subset)


class ConstellationVolume:
    def __init__(self, role, name):
        self.role = role
        self.name = name

    def exists(self):
        return docker_util.volume_exists(self.name)

    def create(self):
        docker_util.ensure_volume(self.name)

    def remove(self):
        docker_util.remove_volume(self.name)


class ConstellationVolumeCollection:
    def __init__(self, volumes):
        if not volumes:
            self.collection = []
        else:
            self.collection = [
                ConstellationVolume(k, v) for k, v in volumes.items()
            ]

    def get(self, role):
        for x in self.collection:
            if x.role == role:
                return x.name
        msg = f"Mount with role '{role}' not defined"
        raise Exception(msg)

    def create(self):
        for vol in self.collection:
            vol.create()

    def remove(self):
        for vol in self.collection:
            vol.remove()


class ConstellationNetwork:
    def __init__(self, name):
        self.name = name

    def exists(self):
        return docker_util.network_exists(self.name)

    def create(self):
        docker_util.ensure_network(self.name)

    def remove(self):
        docker_util.remove_network(self.name)


class ConstellationVolumeMount(_ConstellationMount):
    def __init__(self, name, target, **kwargs):
        self._assert_absolute_path(target)
        self.target = target
        self.name = name
        self.kwargs = kwargs
        self.kwargs["type"] = "volume"

    def to_mount(self, volumes):
        return docker.types.Mount(
            self.target, volumes.get(self.name), **self.kwargs
        )


class ConstellationBindMount(_ConstellationMount):
    def __init__(self, source, target, **kwargs):
        self._assert_absolute_path(target)
        self.target = target
        self._assert_absolute_path(source)
        self.source = source
        self.kwargs = kwargs
        self.kwargs["type"] = "bind"

    def to_mount(self, _volumes):
        return docker.types.Mount(self.target, self.source, **self.kwargs)


def int_into_tuple(i):
    if isinstance(i, int):
        return i, i
    return i


def port_config(ports):
    if not ports:
        return None
    tuple_ports = [int_into_tuple(p) for p in ports]
    return dict(tuple_ports)


def container_ports(ports):
    if not ports:
        return None
    return list(ports.keys())
