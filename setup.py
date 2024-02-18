import codecs
import os.path

import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith("__VERSION__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


setuptools.setup(
    name="aiojlrpy",
    version=get_version("aiojlrpy/__init__.py"),
    author="msp1974",
    author_email="msparker@sky.com",
    description="Async Library for JLRIncontrol",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/msp1974/aiojlrpy",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=["aiohttp>=3.9.3"],
    python_requires=">=3.11",
)
