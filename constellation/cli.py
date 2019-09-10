"""Usage:
  constellation start
"""

import docopt

import constellation


def main(argv=None):
    target, args = parse_args(argv)
    target(*args)


def parse_args(argv):
    args = docopt.docopt(__doc__, argv)
    if args["start"]:
        args = ()
        target = constellation.start
    return target, args
