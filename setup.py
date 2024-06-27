#!/usr/bin/env python3

"""setup.py"""

import setuptools


with open("README.md", "r", encoding="utf8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="roboauto",
    version="0.3.2",
    author="jerryfletcher21",
    author_email="jerryfletcher@cock.email",
    description="robosats cli",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jerryfletcher21/roboauto",
    license="ISC",
    packages=["roboauto"],
    scripts=["bin/roboauto"]
)
