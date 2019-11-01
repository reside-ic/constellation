## Publishing

The python installer is mysterious and is liable to not reflect your sources if old files are around, even if it _seems_ like things have changed.  Deleting some things first helps:

```
rm -rf constellation.egg-info dist
```

But running in a brand new clone seems to be the only safe solution. Be aware that the upload step will upload any old junk in the dist directory and then break subsequent installation, with no warning that what you are doing is going to be a bad idea.

Build the source distribution for publishing

```
python3 setup.py sdist
```

To testing

```
twine upload --repository-url https://test.pypi.org/legacy/ dist/*.tar.gz
```

To do this, the version number **must** be incremented over the published versions ([testing](https://test.pypi.org/project/constellation/), [main index](https://pypi.org/project/constellation/)) - if you forget to increment it the server will reject the upload.

Test the installation

```
docker run --rm -it --entrypoint bash python
```

then

```
pip3 install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple constellation
```

Then upload to the main index

```
twine upload dist/*.tar.gz
```
