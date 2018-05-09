# Alpakka

Python project to generate automated java code skeletons out of YANG statements. Primary purpose is to generate java code for network equipment which could be configured by Netconf/YANG, the code skeletons are prepaired in a way to handle Netconf/YANG requests.

## Getting Started

The following steps whill guide you through the installation process and a basic functional testing. Please be aware that the following instructions are only tested with the referenced versions of python and the required python libraries.

### Prerequisites

To uses the project it is required to install python version 3.5, python pip and git as repository manager.

### Installing

* The first step is to clone the two required the repositories, the first repository is *alpakka* project, it contains the wrapping engine and the required functionality to to map the wrapped YANG statement into different classes and files.

	git clone https://.....
	
* The second repository is the *wools* project, this project containes adaptions on the wrapping engine of the *alpakka* project which are specific for different programming languages and frameworks.

	git clone https://.....
	
* The next step is to install both projects and the required dependencies. It is recommended to install first the *wools* project and afterwards the *alpakka* project.

	pip install <path-to-the-git-directory-of-each-project>
	
* After the installation of both projects is finished it is recommended to check are some importent packages installed in the correct version. The following command displayes all installed python packages

	pip list
	
* The following packages are required in the listed versions all other packages could be installed in the latest versions.

	* python version: 3.5
	* pyang  version: 1.7.3
	
### Running initial tested

* @Thomas: Should the git repository provide a simple Yang statement to make a test with out a specific wool?

### Running Alpakka

The *alpakka* project could be called from the command line terminal and provides the following options

* '<option>' (**required**)
	- explaination
	- explaination
	
* '<option>' (**required**)
	- explaination
	- explaination

