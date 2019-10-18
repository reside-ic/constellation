import pytest

from constellation.constellation import *


def test_container_ports_creates_ports_dictionary():
    assert container_ports([]) is None
    assert container_ports(None) is None
    assert container_ports([80]) == {"80/tcp": 80}
    assert container_ports([80, 443]) == {"80/tcp": 80, "443/tcp": 443}
