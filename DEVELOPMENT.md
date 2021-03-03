# Developing TA-quolab

## Building

You can build the QuoLab add on for Splunk using the following steps:


First install:

    ./build.py && $SPLUNK_HOME/bin/splunk install app $(<.latest_release)

To quickly reload the app on a local Splunk instance during development:

    ./build.py && $SPLUNK_HOME/bin/splunk install app $(<.latest_release) -update 1



## Python packages

List all externally required Python packages in the `requirements.txt` file.
These packages are automatically downloaded and extracted into the `lib` folder of the addon during the build process.
Please be aware of Python 2/3 compatibility concerns when picking external package dependency.

**Gotchas:**  Avoid packages that *only* work on a specific version of Python or has OS-specific compiled libraries.
Python 2.7 support is going away for more and more packages, so pinning older versions may be required until targeting only Splunk 8+ for compatibility.
The default build script only builds with a single version of Python, and doesn't attempt to separate packages based on OS or Python version.



## Development

Setup a local virtual environment in the top level of the package to install the necessary build and runtime requirements.

    python -m virtualenv venv
    . venv/bin/activate
    python -m pip install -U -r requirements-dev.txt


## Tools

 * [Cookiecutter](https://github.com/audreyr/cookiecutter) is use to kickstart the development of new addons.
 * [bump2version](https://pypi.org/project/bump2version/) Version bump your addon with a single command!
 * [ksconf](https://ksconf.readthedocs.io/) Kintyre Splunk CONF tool
 * [pre-commit](https://pre-commit.com/) a framework for managing and maintaining pre-commit hooks for git.
