#!/usr/bin/env python3
"""Setup for pip installing package: {mp:formatted_name}.

**Author: Jonathan Delgado**

"""
from setuptools import setup, find_packages

setup(
    name='{mp:formatted_name}',
    version='0.0.0.0',
    description='{mp:name}',
    license='GNU GENERAL PUBLIC LICENSE',
    url='https://github.com/otanan/{mp:formatted_name}',
    author='Jonathan Delgado',
    author_email='jonathan.delgado@uci.edu',
    keywords=[],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: GNU GENERAL PUBLIC LICENSE',
        'Programming Language :: Python :: 3.10',
    ],
    # download_url='https://github.com/otanan/{mp:formatted_name}/archive/refs/tags/0.0.1.1.tar.gz',
    # packages=find_packages(),
    packages=[
    ],
    install_requires=[
        # External packages
    ],
)