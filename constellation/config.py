import base64
import docker
import pickle

import constellation.docker_util as docker_util
from constellation.config_util import \
    DockerImageReference, \
    config_build, \
    config_string, \
    read_yaml


class ConstellationMetaConfiguration:
    """Developer-written configuration for a configuration"""
    def __init__(self, name, basename, container, container_path=None,
                 default_container_prefix=None):
        self.name = name
        self.basename = basename
        self.container = container
        if not container_path:
            container_path = "/{}.yml".format(basename)
        self.container_path = container_path
        self.default_container_prefix = default_container_prefix


class ConstellationConfiguration:
    def __init__(self, path, meta):
        self.meta = meta
        self.path = path
        self.data = read_yaml("{}/{}.yml".format(path, meta.basename))
        self.container_prefix = container_prefix(self.data, meta)

    def build(self, extra=None, options=None):
        return config_build(self.path, self.data, extra, options)

    def fetch(self):
        cl = docker.client.from_env()
        try:
            container = cl.containers.get(self.name_persist())
        except docker.errors.NotFound:
            return None
        txt = docker_util.string_from_container(container,
                                                self.meta.container_path)
        return pickle.loads(base64.b64decode(txt))

    def save(self, data):
        cl = docker.client.from_env()
        container = cl.containers.get(self.name_persist())
        txt = base64.b64encode(pickle.dumps(data)).decode("utf8")
        docker_util.string_into_container(txt, container,
                                          self.meta.container_path)

    def name_persist(self):
        return "{}_{}".format(self.container_prefix, self.meta.container)


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
        cl = docker.client.from_env()
        docker_util.image_pull(cl, self.name, str(self.image))

    def exists(self, prefix):
        cl = docker.client.from_env()
        return docker_util.container_exists(self.name_external(prefix))

    def start(self, prefix, network, volumes):
        cl = docker.client.from_env()
        nm = self.name_external(prefix)
        print("Starting {}".format(self.name))
        mounts = [x.to_mount(volumes) for x in self.mounts]
        x = cl.containers.run(str(self.image), self.args, name=nm,
                              mounts=mounts, detach=True, network="none",
                              ports=self.ports, environment=self.environment)
        ## There is a bit of a faff here, because I do not see how we
        ## can get the container onto the network *and* alias it
        ## without having 'create' put it on a network first.  This
        ## must be possible, but the SDK docs are a bit vague on the
        ## topic.  So we create the container on the 'none' network,
        ## then disconnect it from that network, then attach it to our
        ## network with an appropriate alias (the docs suggest using
        ## an approch that uses the lower level api but I can't get
        ## that working).
        cl.networks.get("none").disconnect(x)
        cl.networks.get(network.name).connect(x, aliases=[self.name])
        x.reload()
        if self.configure:
            self.configure(x, self.image)

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

    def start(self, prefix, network, volumes):
        self._apply("start", prefix, network, volumes)


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


def container_prefix(data, meta):
    default = meta.default_container_prefix
    required = default is None
    given = config_string(data, ["docker", "container_prefix"], required)
    return given or meta.default_container_prefix


# only handles the simple case of "expose a port" and not "remap a
# port", and assumes the port is to be exposed onto all interfaces.
def container_ports(ports):
    if not ports:
        return None
    ret = {}
    for p in ports:
        ret["{}/tcp".format(p)] = p
    return ret
