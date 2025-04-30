## constellation

[![Build Status](https://github.com/reside-ic/constellation/actions/workflows/test.yml/badge.svg)](https://github.com/reside-ic/constellation/actions)
[![codecov.io](https://codecov.io/github/reside-ic/constellation/coverage.svg?branch=master)](https://codecov.io/github/reside-ic/constellation?branch=master)

An alternative to docker-compose more suited to our needs. A package for managing "constellations" of docker containers that need various bespoke bits of logic when being brought up and down.

## Installation

```
pip install constellation
```

## Publishing

Automatically publish to [PyPI](https://pypi.org/project/constellation).  Assuming a version number `0.1.2`:

* Create a [release on github](https://github.com/reside-ic/constellation/releases/new)
* Choose a tag -> Create a new tag: `v0.1.2`
* Use this version as the description
* Optionally describe the release
* Click "Publish release"
* This triggers the release workflow and the package will be available on PyPI in a few minutes

Settings are configured [here on PyPI](https://pypi.org/manage/project/constellation/settings/publishing)
