import pytest

from constellation.util import *


def test_image_reference_can_convert_to_string():
    ref = ImageReference("repo", "name", "tag")
    assert str(ref) == "repo/name:tag"


def test_tabulate():
    assert tabulate([]) == {}
    assert tabulate(["a"]) == {"a": 1}
    assert tabulate(["a", "a", "b"]) == {"a": 2, "b": 1}
    assert tabulate(["a", "a", "b", "a"]) == {"a": 3, "b": 1}
