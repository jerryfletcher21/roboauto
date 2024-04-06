#!/usr/bin/env python3

"""setup.py"""

import setuptools


setuptools.setup(
    name="roboauto",
    version="0.1",
    description="robosats cli",
    license="ISC",
    author="jerryfletcher21",
    author_email="jerryfletcher@cock.email",
    packages=["roboauto"],
    scripts=["bin/roboauto"]
)
