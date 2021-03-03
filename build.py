#!/usr/bin/env python
import sys
from ksconf.builder import BuildManager, VERBOSE, QUIET, default_cli
from ksconf.builder.steps import clean_build, copy_files, pip_install

manager = BuildManager()

APP_FOLDER = "TA-quolab"
SPL_NAME = "ta_quolab-{{version}}.tgz"
SOURCE_DIR = "."

REQUIREMENTS = "requirements.txt"

# Files needed to support the build process (but not in the final package)
BUILD_FILES = [
    REQUIREMENTS,
]

COPY_FILES = [
    "README.md",
    "bin/*.py",
    "default/",
    "metadata/*.meta",
    "static/",
    "lookups/*.csv",
    "appserver/",
    "README/*.spec",
] + BUILD_FILES


@manager.cache([REQUIREMENTS], ["lib/"], timeout=7200)
def python_packages(step):
    # Sticking with the defaults
    pip_install(step, REQUIREMENTS, "lib",
                handle_dist_info="remove"  # vs 'rename'
                )


def package_spl(step):
    step.run(sys.executable, "-m", "ksconf", "package",
             "--file", step.dist_path / SPL_NAME,   # Path to created tarball
             "--app-name", APP_FOLDER,              # Top-level directory name
             "--block-local",                       # Build from version control should have no 'local' folder
             "--release-file",  step.dist_path.parent / ".latest_release",
             ".")


def build(step, args):
    """ Build process """
    # Step 1:  Clean/create build folder
    clean_build(step)

    # Step 2:  Copy files from source to build folder
    copy_files(step, COPY_FILES)

    # Step 3:  Install Python package dependencies
    python_packages(step)

    # Step 4: Build tarball
    package_spl(step)


if __name__ == '__main__':
    # Tell build manager where stuff lives
    manager.set_folders(SOURCE_DIR, "build", "dist")

    # Launch build CLI
    default_cli(manager, build)