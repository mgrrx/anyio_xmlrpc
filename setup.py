from setuptools import find_packages, setup

setup(
    name="anyio_xmlrpc",
    version="0.1.0",
    author="Markus Grimm",
    license="MIT",
    description="AnyIO xmlrpc library",
    long_description="AnyIO xmlrpc library",
    platforms="all",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    include_package_data=True,
    zip_safe=False,
    package_data={"anyio_xmlrpc": ["py.typed", "xmlrpc.rng"]},
    packages=find_packages(exclude=("tests",)),
    install_requires=("anyio", "asks", "h11", "xmlrpcproto"),
    python_requires=">=3.5",
)
