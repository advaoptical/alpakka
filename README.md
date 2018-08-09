# Alpakka

> Licensed under the [Apache License, Version 2.0][license]

[license]: http://www.apache.org/licenses/LICENSE-2.0

[![Supported Python versions][pyversions]][python]
[![PyPI package version][version]][pypi]

[pyversions]: https://img.shields.io/pypi/pyversions/alpakka.svg

[python]: https://python.org

[version]: https://img.shields.io/pypi/v/alpakka.svg

[pypi]: https://pypi.python.org/pypi/alpakka

[![Travis CI build status][status]][travis]

[status]: https://travis-ci.org/advaoptical/alpakka.svg?branch=master

[travis]: https://travis-ci.org/advaoptical/alpakka

Alpakka is a python project that extends [pyang] to automatically generate code skeletons from YANG modules. The focus is on code stubs for the configuration of networks and network devices, which are controlled by NETCONF or RESCONF.

[pyang]: https://github.com/mbj4668/pyang

## Getting Started

The following steps guide you through the installation process. Please be aware that the following instructions are only tested with the referenced versions of python and the required python libraries.

### Prerequisites

Python (version 3.5 or newer), pip and git are required to follow the guide and use the code from this repository.

### Installing

* The first step is to clone the two required repositories. The first repository is the `alpakka` project. It contains the wrapping engine and the basic functionality to map YANG statements to their wrapped representation for the code generation step.

  ```console
  git clone https://github.com/advaoptical/alpakka.git
  ```

* The second step is to clone the `wools` project. It adapts the wrapping engine of `alpakka` by applying specific handling for different programming languages and frameworks and implements the code generation process itself.

  ```console
  git clone https://github.com/advaoptical/wools.git
  ```

* The next step is to install both projects and the required dependencies. It is recommended to install the *alpakka* project first and then the `wools` project. An example is given assuming that you cloned both repositories into the current folder. In case you want to work on the code of *alpakka* the `-e` flag can be used for the pip commands.

  ```console
  pip install ./alpakka
  pip install ./wools
  ```

* After the installation of both projects is finished, you can verify that everything is installed correctly by listing all installed python packages:

  ```console
  pip list
  ```

## Running Alpakka

`alpakka` can be launched from the command line by typing:

```console
alpakka <options> <YANG source file>
```

### Available Options

`alpakka` provides the following command line options:

* `-w`, `--wool` (**required**)

  * The wool used for knitting the code
  * specifies the required wool for the target programming language and framework

* `--output-path` (**required**)

  * output path for the generated classes
  * specifies the root directory used for the code generation

* `-i`, `--interactive`

  * run alpakka in interactive mode by starting an IPython shell before template generation

* `--configuration-file-location`

  * path of the wool configuration file

## Known Limitations

In some cases, `alpakka` does not provide the correct result if augmentation is used. This will be fixed in one of the upcoming releases.
