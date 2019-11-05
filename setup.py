from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

requirements = [
    "docker",
    "hvac",
    "pytest",
    "pyyaml",
    "vault_dev"]

setup(name="constellation",
      version="0.0.3",
      description="Deploy scripts for constellations of docker containers",
      long_description=long_description,
      classifiers=[
          "Programming Language :: Python :: 3",
          "License :: OSI Approved :: MIT License",
          "Operating System :: OS Independent",
      ],
      url="https://github.com/reside-ic/constellation",
      author="Rich FitzJohn",
      author_email="r.fitzjohn@imperial.ac.uk",
      license='MIT',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      # Extra:
      long_description_content_type="text/markdown",
      setup_requires=["pytest-runner"],
      tests_require=[
          "vault_dev",
          "pytest"
      ],
      install_requires = requirements)
