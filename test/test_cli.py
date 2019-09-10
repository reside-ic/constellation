import io
from contextlib import redirect_stdout

import constellation
import constellation.cli


def test_cli_basic_usage():
    f = io.StringIO()
    with redirect_stdout(f):
        constellation.cli.main(["start"])
    out = f.getvalue()
    assert out.strip() == "Hello constellation world"
