import setuptools


with open("README.md", "r", encoding="UTF-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aiojlrpy",
    version="0.1.0",
    author="msp1974",
    author_email="msparker@sky.com",
    description="Async Library for JLRIncontrol",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/msp1974/aiojlrpy",
    install_requires=["aiohttp>=3.9.3"],
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Development Status :: 2 - Pre-Alpha",
    ],
)
