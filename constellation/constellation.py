import docker

import constellation.docker_util as docker_util


class Constellation:
    def __init__(self, name, prefix, containers, network, volumes, data=None):
        self.data = data

        assert type(name) is str
        self.name = name

        assert type(prefix) is str
        self.prefix = prefix

        assert type(network) is str
        self.network = ConstellationNetwork(network)

        if not volumes:
            volumes = []
        else:
            volumes = [ConstellationVolume(k, v) for k, v in
                       volumes.items()]
        self.volumes = ConstellationVolumeCollection(volumes)

        for x in containers:
            assert type(x) is ConstellationContainer
        self.containers = ConstellationContainerCollection(containers)

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
            x_container = x.get(self.prefix)
            x_status = x_container.status if x_container else "missing"
            x_name = x.name_external(self.prefix)
            print("    - {} ({}): {}".format(x.name, x_name, x_status))

    def start(self, pull_images=False):
        if any(self.containers.exists(self.prefix)):
            raise Exception("Some containers exist")
        if pull_images:
            self.containers.pull_images()
        self.network.create()
        self.volumes.create()
        self.containers.start(self.prefix, self.network, self.volumes,
                              self.data)

    def stop(self, kill=False, remove_network=False, remove_volumes=False):
        if kill:
            self.containers.kill(self.prefix)
        else:
            self.containers.stop(self.prefix)
        self.containers.remove(self.prefix)
        if remove_network:
            self.network.remove()
        if remove_volumes:
            self.volumes.remove()

    def destroy(self):
        self.stop(True, True, True)


class ConstellationContainer:
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

    def pull(self):
        docker_util.image_pull(self.name, str(self.image))

    def exists(self, prefix):
        return docker_util.container_exists(self.name_external(prefix))

    def start(self, prefix, network, volumes, data=None):
        cl = docker.client.from_env()
        nm = self.name_external(prefix)
        print("Starting {} ({})".format(self.name, str(self.image)))
        mounts = [x.to_mount(volumes) for x in self.mounts]
        x = cl.containers.run(str(self.image), self.args, name=nm,
                              auto_remove=True, detach=True, mounts=mounts,
                              network="none", ports=self.ports,
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

    def stop(self, prefix):
        container = self.get(prefix)
        if container and container.status == "running":
            print("Stopping '{}'".format(self.name))
            container.stop()

    def kill(self, prefix):
        container = self.get(prefix)
        if container and container.status == "running":
            print("Killing '{}'".format(self.name))
            container.kill()

    def remove(self, prefix):
        container = self.get(prefix)
        if container:
            print("Removing '{}'".format(self.name))
            container.remove()


class ConstellationContainerCollection:
    def __init__(self, collection):
        self.collection = collection

    def exists(self, prefix):
        return [x.exists(prefix) for x in self.collection]

    def _apply(self, method, *args):
        for x in self.collection:
            x.__getattribute__(method)(*args)

    def pull_images(self):
        self._apply("pull")

    def stop(self, prefix):
        self._apply("stop", prefix)

    def kill(self, prefix):
        self._apply("kill", prefix)

    def remove(self, prefix):
        self._apply("remove", prefix)

    def start(self, prefix, network, volumes, data=None):
        self._apply("start", prefix, network, volumes, data)


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
    def __init__(self, collection):
        self.collection = collection

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


# only handles the simple case of "expose a port" and not "remap a
# port", and assumes the port is to be exposed onto all interfaces.
def container_ports(ports):
    if not ports:
        return None
    ret = {}
    for p in ports:
        ret["{}/tcp".format(p)] = p
    return ret
