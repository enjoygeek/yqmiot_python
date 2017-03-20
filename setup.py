# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='yqmiot',
    version='1.0.1',
    description='the yqmiot client.',
    author='yueqiumao',
    author_email='u2nn@qq.com',
    install_requires=['paho-mqtt'],
    py_modules = ['yqmiot'],
    include_package_data=True,
    zip_safe=False,
    url='http://yqmiot.com',
    keywords='yqmiot'
)

