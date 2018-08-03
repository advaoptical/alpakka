# Alpakka

[![](https://img.shields.io/pypi/pyversions/alpakka.svg)](
	https://python.org)
[![](https://img.shields.io/pypi/v/alpakka.svg)](
	https://pypi.python.org/pypi/alpakka)

> Licensed under the [Apache License, Version 2.0](
	http://www.apache.org/licenses/LICENSE-2.0)

[![Travis CI Build Status](
	https://travis-ci.org/advaoptical/alpakka.svg?branch=master)](
		https://travis-ci.org/advaoptical/alpakka)

Alpakka is a python project that extends pyang to automatically generate code skeletons from YANG statements. The primary goal is to generate code skeletons for the configuration of networks and network devices which are controlled by NETCONF or RESCONF.

## Getting Started

The following steps guide you through the installation process. Please be aware that the following instructions are only tested with the referenced versions of python and the required python libraries.

### Prerequisites

Python (version 3.5 or newer), pip and git are required to use this project.

### Installing

* The first step is to clone the two required repositories. The first repository is the *alpakka* project. It contains the wrapping engine and the required functionality to map YANG statements into the wrapped representation for the code generation step.

```
	git clone https://github.com/advaoptical/alpakka.git
```

* The second step is to clone the *wools* project. It adapts the wrapping engine of the *alpakka* project by applying specific handling for different programming languages and frameworks and implements the code generation process itself.

```
	git clone https://github.com/advaoptical/wools.git
```

* The next step is to install both projects and the required dependencies. It is recommended to install the *alpakka* project first and then the *wools* project. An example is given assuming that you cloned both repositories in your current folder. In case you want to work on the code of *alpakka* the `-e` flag can be used for the pip commands.

```
	cd alpakka
	pip install .
	cd ../wools
	pip install .
```

* After the installation of both projects is finished, it is recommended to verify that the correct version was installed. The following command lists all installed python packages:

```
	pip list
```

* The following packages are required in the listed versions all other packages could be installed in the latest versions.

	* python version: 3.5
	* pyang version: 1.7.3

## Running Alpakka

*alpakka* can be launched from the command line by typing:
```
	alpakka <options> <YANG source file>
```
### Available Options

The *alpakka* project provides the following command line options

* '-w; --wool' (**required**)
	- The wool used for knitting the code
	- specifies the required wool for the target programming language and framework

* '--output-path' (**required**)
	- output path for the generated classes
	- specifies the root directory used for the code generation

* '-i; --interactive'
	- run alpakka in interactive mode by starting an IPython shell before template generation

* '--configuration-file-location'
	- path of the wool configuration file