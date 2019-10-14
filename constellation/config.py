import base64
import docker
import pickle

import constellation.docker_util as docker_util
from constellation.config_util import \
    DockerImageReference \
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
    def __init__(self, prefix, network, name, image, args=None,
                 mounts=None, ports=None, environment=None, configure=None,
                 volumes=None):
        self.network = network
        self.name = name
        self.name_external = "{}_{}".format(prefix, self.name)
        self.image = image
        self.args = args
        if mounts:
            mounts = [x.to_mount(volumes) for x in mounts]
        self.mounts = mounts
        self.ports = ports
        self.environment = environment
        self.configure = configure

    def pull(self):
        cl = docker.client.from_env()
        docker_util.image_pull(cl, self.name, str(self.image))

    def exists(self):
        cl = docker.client.from_env()
        return docker_util.container_exists(cl, self.name_external)

    def start(self, data=None):
        cl = docker.client.from_env()
        nm = self.name_external
        print("Starting {}".format(self.name))
        x = cl.containers.run(str(self.image), self.args, name=nm,
                              mounts=self.mounts, detach=True, network="none",
                              environment=self.environment)
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
        cl.networks.get(self.network.name).connect(x, aliases=[self.name])
        x.reload()
        if self.configure:
            self.configure(x, self.image, data)

    def get(self):
        client = docker.client.from_env()
        try:
            return client.containers.get(self.name_external)
        except docker.errors.NotFound:
            return None

    def stop(self):
        container = self.get()
        if container:
            print("Stopping '{}'".format(self.name))
            container.stop()

    def kill(self):
        container = self.get()
        if container:
            print("Killing '{}'".format(self.name))
            container.kill()

    def remove(self):
        container = self.get()
        if container:
            print("Removing '{}'".format(self.name))
            container.remove()


class ConstellationContainerCollection:
    def __init__(self, collection):
        self.collection = collection

    def exists(self):
        return [x.exists() for x in self.collection]

    def _apply(self, method):
        for x in self.collection:
            x.__getattribute__(method)()

    def pull_images(self):
        self._apply("pull")

    def stop(self):
        self._apply("stop")

    def kill(self):
        self._apply("kill")

    def remove(self):
        self._apply("remove")

    def start(self):
        self._apply("start")


class ConstellationVolume:
    def __init__(self, role, name):
        self.role = role
        self.name = name

    def exists(self):
        return docker_util.volume_exists(docker.client.from_env(), self.name)

    def create(self):
        docker_util.ensure_volume(docker.client.from_env(), self.name)

    def remove(self):
        docker_util.remove_volume(docker.client.from_env(), self.name)


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


class ConstellationNetwork:
    def __init__(self, name):
        self.name = name

    def exists(self):
        return docker_util.network_exists(docker.client.from_env(), self.name)

    def create(self):
        docker_util.ensure_network(docker.client.from_env(), self.name)

    def remove(self):
        docker_util.remove_network(docker.client.from_env(), self.name)


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
