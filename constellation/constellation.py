import constellation.config as config
import constellation.docker_util as docker_util

class Constellation:
    def __init__(self, name, prefix, containers, network, volumes):
        assert type(name) is str
        self.name = name

        assert type(prefix) is str
        self.prefix = prefix

        assert type(network) is str
        self.network = config.ConstellationNetwork(network)

        if not volumes:
            volumes = []
        else:
            volumes = [config.ConstellationVolume(k, v) for k, v in
                       volumes.items()]
        self.volumes = config.ConstellationVolumeCollection(volumes)

        for x in containers:
            assert type(x) is config.ConstellationContainer
        self.containers = config.ConstellationContainerCollection(containers)

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
        self.containers.start(self.prefix, self.network, self.volumes)

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
