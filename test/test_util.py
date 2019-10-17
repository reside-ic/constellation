import pytest

from constellation.util import *


def test_image_reference_can_convert_to_string():
    ref = ImageReference("repo", "name", "tag")
    assert str(ref) == "repo/name:tag"
