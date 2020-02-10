import docker

import constellation.docker_util as docker_util
import constellation.vault as vault

from constellation.util import tabulate, rand_str


class Constellation:
    def __init__(self, name, prefix, containers, network, volumes, data=None,
                 vault_config=None):
        self.data = data

        assert type(name) is str
        self.name = name

        assert type(prefix) is str
        self.prefix = prefix

        assert type(network) is str
        self.network = ConstellationNetwork(network)
        self.volumes = ConstellationVolumeCollection(volumes)

        for x in containers:
            assert type(x) in [ConstellationContainer, ConstellationService]

        self.containers = ConstellationContainerCollection(containers)
        self.vault_config = vault_config

    def status(self):
        nw_name = self.network.name
        nw_status = "created" if docker_util.network_exists(nw_name) \
                    else "missing"
        print("Constellation {}".format(self.name))
        print("  * Network:")
        print("    - {}: {}".format(nw_name, nw_status))
        print("  * Volumes:")
        for v in self.volumes.collection:
            v_status = "created" if docker_util.volume_exists(v.name) \
                    else "missing"
            print("    - {} ({}): {}".format(v.role, v.name, v_status))
        print("  * Containers:")
        for x in self.containers.collection:
            x_name = x.name_external(self.prefix)
            x_status = x.status(self.prefix)
            print("    - {} ({}): {}".format(x.name, x_name, x_status))

    def start(self, pull_images=False, subset=None):
        if subset is None and any(self.containers.exists(self.prefix)):
            raise Exception("Some containers exist")
        if self.vault_config:
            vault.resolve_secrets(self.data, self.vault_config.client())
        if pull_images:
            self.containers.pull_images()
        self.network.create()
        self.volumes.create()
        self.containers.start(self.prefix, self.network, self.volumes,
                              self.data, subset)

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


class ConstellationContainer:
    """For ports, to remap a port pass a tuple (port_container,
    port_host), such as:

    ports=[80, (2222, 3333)]

    which will expose port 80 (same port on both the container and
    host) and expose port 2222 in the container as 3333 on the host.
    """
    def __init__(self, name, image, args=None,
                 mounts=None, ports=None, environment=None, configure=None):
        self.name = name
        self.image = image
        self.args = args
        self.mounts = mounts or []
        self.ports = container_ports(ports)
        self.environment = environment
        self.configure = configure

    def name_external(self, prefix):
        return "{}_{}".format(prefix, self.name)

    def pull_image(self):
        docker_util.image_pull(self.name, str(self.image))

    def exists(self, prefix):
        return docker_util.container_exists(self.name_external(prefix))

    def start(self, prefix, network, volumes, data=None):
        cl = docker.client.from_env()
        nm = self.name_external(prefix)
        print("Starting {} ({})".format(self.name, str(self.image)))
        mounts = [x.to_mount(volumes) for x in self.mounts]
        x = cl.containers.run(str(self.image), self.args, name=nm,
                              detach=True,
                              mounts=mounts, network="none", ports=self.ports,
                              environment=self.environment)
        # There is a bit of a faff here, because I do not see how we
        # can get the container onto the network *and* alias it
        # without having 'create' put it on a network first.  This
        # must be possible, but the SDK docs are a bit vague on the
        # topic.  So we create the container on the 'none' network,
        # then disconnect it from that network, then attach it to our
        # network with an appropriate alias (the docs suggest using an
        # approch that uses the lower level api but I can't get that
        # working).
        cl.networks.get("none").disconnect(x)
        cl.networks.get(network.name).connect(x, aliases=[self.name])
        x.reload()
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
            print("Removing '{}'".format(self.name))
            with docker_util.ignoring_missing():
                container.remove()


# This could be achievd by inheriting from ConstellationContainer but
# this seems more like a has-a than an is-a relationship.
class ConstellationService():
    def __init__(self, name, image, scale, **kwargs):
        self.name = name
        self.image = image
        self.scale = scale
        self.kwargs = kwargs
        self.base = ConstellationContainer(name, image, **kwargs)

    def name_external(self, prefix):
        return "{}_<i>".format(self.base.name_external(prefix))

    def pull_image(self):
        self.base.pull_image()

    def exists(self, prefix):
        return bool(self.get(prefix))

    def start(self, prefix, network, volumes, data=None):
        print("Starting *service* {}".format(self.name))
        for i in range(self.scale):
            name = "{}_{}".format(self.name, rand_str(8))
            container = ConstellationContainer(name, self.image, **self.kwargs)
            container.start(prefix, network, volumes, data)

    def get(self, prefix, stopped=False):
        pattern = self.base.name_external(prefix) + "_"
        return docker_util.containers_matching(pattern, stopped)

    def status(self, prefix):
        status = tabulate([x.status for x in self.get(prefix)])
        if status:
            ret = ", ".join(["{} ({})".format(k, v)
                             for k, v in status.items()])
        else:
            ret = "missing"
        return ret

    def stop(self, prefix, kill=False):
        for x in self.get(prefix):
            docker_util.container_stop(x, kill, self.name)

    def remove(self, prefix):
        containers = self.get(prefix, True)
        if containers:
            print("Removing '{}'".format(self.name))
            for x in containers:
                x.remove()


class ConstellationContainerCollection:
    def __init__(self, collection):
        self.collection = collection

    def find(self, name):
        for x in self.collection:
            if x.name == name:
                return x
        raise Exception("Container '{}' not defined".format(name))

    def get(self, name, prefix, container=True):
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
            self.collection = [ConstellationVolume(k, v) for k, v in
                               volumes.items()]

    def get(self, role):
        for x in self.collection:
            if x.role == role:
                return x.name
        raise Exception("Mount with role '{}' not defined".format(role))

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


class ConstellationMount:
    def __init__(self, name, path, **kwargs):
        self.name = name
        self.path = path
        self.kwargs = kwargs

    def to_mount(self, volumes):
        return docker.types.Mount(self.path, volumes.get(self.name),
                                  **self.kwargs)


def container_ports(ports):
    if not ports:
        return None
    ret = {}
    for p in ports:
        if type(p) is int:
            p = (p, p)
        p_container, p_host = p
        ret["{}/tcp".format(p_container)] = p_host
    return ret
