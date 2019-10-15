import constellation.config as config

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
        pass

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
