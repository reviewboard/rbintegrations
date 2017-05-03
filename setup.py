#!/usr/bin/env python

from reviewboard.extensions.packaging import setup
from setuptools import find_packages

from rbintegrations import get_package_version


PACKAGE = 'rbintegrations'

setup(
    name=PACKAGE,
    version=get_package_version(),
    description=('A set of third-party service integrations for Review Board '
                 '3.0+.'),
    url='https://www.reviewboard.org/',
    author='Beanbag, Inc.',
    author_email='support@beanbaginc.com',
    maintainer='Beanbag, Inc.',
    maintainer_email='support@beanbaginc.com',
    packages=find_packages(),
    install_requires=[
        'PyYAML>=3.12',
    ],
    entry_points={
        'reviewboard.extensions':
            '%s = rbintegrations.extension:RBIntegrationsExtension' % PACKAGE,
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Review Board',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ]
)
