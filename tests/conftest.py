import vault_dev


# https://stackoverflow.com/a/35394239
def pytest_sessionstart(_session):
    vault_dev.ensure_installed()
