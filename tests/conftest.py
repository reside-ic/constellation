import vault_dev


# https://stackoverflow.com/a/35394239
#
# the lint exception is required here as session must be the name of
# the argument but we don't actually use it
def pytest_sessionstart(session):  # noqa: ARG001
    vault_dev.ensure_installed()
