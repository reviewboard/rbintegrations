#!/usr/bin/env python3

from reviewboard.extensions.packaging import setup
from setuptools import find_packages

from rbintegrations import get_package_version


PACKAGE = 'rbintegrations'


with open('README.rst', 'r') as fp:
    long_description = fp.read()


setup(
    name=PACKAGE,
    version=get_package_version(),
    description=(
        'A set of third-party service integrations for Review Board 5.0+.'
    ),
    long_description=long_description,
    url='https://www.reviewboard.org/',
    author='Beanbag, Inc.',
    author_email='support@beanbaginc.com',
    maintainer='Beanbag, Inc.',
    maintainer_email='support@beanbaginc.com',
    packages=find_packages(),
    install_requires=[
        'asana',
        'PyYAML>=3.12',
    ],
    entry_points={
        'reviewboard.extensions':
            '%s = rbintegrations.extension:RBIntegrationsExtension' % PACKAGE,
    },
    python_requires='>=3.7',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Review Board',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Communications :: Chat',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
    ]
)
