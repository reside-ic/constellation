class ImageReference:
    def __init__(self, repo, name, tag):
        self.repo = repo
        self.name = name
        self.tag = tag

    def __str__(self):
        return "{}/{}:{}".format(self.repo, self.name, self.tag)


def tabulate(x):
    ret = {}
    for el in x:
        if el in ret.keys():
            ret[el] += 1
        else:
            ret[el] = 1
    return ret
