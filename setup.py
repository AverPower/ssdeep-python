#!/usr/bin/env python
import errno
import glob
import os
import subprocess
import sys
from sysconfig import get_config_vars

from setuptools import Distribution as _Distribution
from setuptools import setup
from setuptools.command.build_ext import build_ext as _build_ext

try:
    from setuptools.command.build_clib import build_clib as _build_clib
except ImportError:
    # We ignore type checking because mypy shows an import error
    from distutils.command.build_clib import build_clib as _build_clib  # type: ignore

base_dir = os.path.dirname(__file__)
src_dir = os.path.join(base_dir, "src")
# sys.path.insert(0, base_dir)

use_system_lib = True
if os.environ.get("BUILD_LIB") == "1":
    use_system_lib = False


class BuildClib(_build_clib):
    def build_libraries(self, libraries):
        raise Exception("build_libraries")

    def check_library_list(self, libraries):
        raise Exception("check_library_list")

    def get_library_names(self):
        return ["fuzzy"]

    def get_source_files(self):
        files = glob.glob(os.path.relpath("src/ssdeep-lib/*"))
        files += glob.glob(os.path.relpath("src/ssdeep-lib/m4/*"))
        return files

    def run(self):
        if use_system_lib:
            return

        build_env = {
            key: val
            for key, val in get_config_vars().items()
            if key in ("LDFLAGS", "CFLAGS", "CC", "CCSHARED", "LDSHARED")
            and key not in os.environ
        }
        os.environ.update(build_env)

        build_temp = os.path.abspath(self.build_temp)
        try:
            os.makedirs(build_temp)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        # libtoolize: Install required files for automake
        returncode = subprocess.call(
            "(cd src/ssdeep-lib && libtoolize && autoreconf --force)",
            shell=True
        )
        if returncode != 0:
            # try harder
            returncode = subprocess.call(
                "(cd src/ssdeep-lib && automake --add-missing && autoreconf --force)",
                shell=True
            )
            if returncode != 0:
                sys.exit("Failed to reconfigure the project build.")

        configure_cmd = os.path.abspath(os.path.relpath("src/ssdeep-lib/configure"))

        configure_flags = [
            "--disable-shared",
            "--enable-static",
            "--disable-debug",
            "--disable-dependency-tracking",
            "--with-pic",
        ]

        returncode = subprocess.call(
            [configure_cmd]
            + configure_flags
            + ["--prefix", os.path.abspath(self.build_clib)],
            cwd="src/ssdeep-lib"
        )
        returncode = subprocess.call(
            ["make"],
            cwd="src/ssdeep-lib"
        )
        returncode = subprocess.call(
            ["make", "install"],
            cwd="src/ssdeep-lib"
        )

        if returncode != 0:
            sys.exit("Failed while building ssdeep lib.")


class BuildExt(_build_ext):
    def run(self):
        if self.distribution.has_c_libraries():
            build_clib = self.get_finalized_command("build_clib")
            self.include_dirs.append(
                os.path.join(build_clib.build_clib, "include"),
            )
            self.library_dirs.insert(
                0,
                os.path.join(build_clib.build_clib, "lib64"),
            )
            self.library_dirs.insert(
                0,
                os.path.join(build_clib.build_clib, "lib"),
            )

            # ToDo: Is there a better way?
            for ext in self.extensions:
                ext.extra_objects += get_objects()

        return _build_ext.run(self)


class Distribution(_Distribution):
    def has_c_libraries(self):
        return not use_system_lib


def get_objects():
    objects = glob.glob("src/ssdeep-lib/.libs/*.o")
    if len(objects) > 0:
        return objects
    return glob.glob("src/ssdeep-lib/.libs/*.obj")


about = {}
with open(os.path.join(src_dir, "ssdeep", "__about__.py")) as f:
    exec(f.read(), about)

with open(os.path.join(base_dir, "README.rst")) as f:
    long_description = f.read()

setup(
    name=about["__title__"],
    version=about["__version__"],
    python_requires=">=3.10",

    description=about["__summary__"],
    long_description=long_description,
    # The distribution contains the LGPL-licensed Python wrapper and the
    # bundled GPL-licensed ssdeep library.
    license="LGPL-3.0-or-later AND GPL-2.0-only",
    license_files=[
        "LICENSE",
        "src/ssdeep-lib/COPYING",
    ],
    url=about["__uri__"],

    zip_safe=False,
    author=about["__author__"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="ssdeep",
    install_requires=[
        "cffi>=2.0.0",
    ],
    extras_require={
        "docstest": [
            "doc8",
            "readme_renderer >= 16.0",
            "sphinx",
            "sphinx_rtd_theme",
        ],
    },
    packages=[
        "ssdeep"
    ],
    include_package_data=True,
    cffi_modules=["src/ssdeep/_build.py:ffi"],
    package_dir={"": "src"},
    cmdclass={
        "build_clib": BuildClib,
        "build_ext": BuildExt
    },
    distclass=Distribution,
)
