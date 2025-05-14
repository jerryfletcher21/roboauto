#!/usr/bin/env python3

"""setup.py"""

import setuptools


with open("README.md", "r", encoding="utf8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="roboauto",
    version="0.4.0",
    author="jerryfletcher21",
    author_email="jerryfletcher@cock.email",
    description="robosats cli",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jerryfletcher21/roboauto",
    license="ISC",
    packages=["roboauto"],
    scripts=["bin/roboauto"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Programming Language :: Python",
        "Programming Language :: Unix Shell",
        "Topic :: Software Development",
        "Topic :: System :: Shells",
        "Topic :: Utilities"
    ]
)
