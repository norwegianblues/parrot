# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

########################################################################
# Copyright (c) 2013 Ericsson AB
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v1.0
# which accompanies this distribution, and is available at
# http://www.eclipse.org/legal/epl-v10.html
#
# Contributors:
#    Ericsson Research - initial implementation
#
########################################################################

from setuptools import setup, find_packages

setup(
    name="Parrot",
    version="0.1.0",
    description="An Internet of Things simulator",
    license="EPL 1.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'web': [
            'parrot/web/*',
            'parrot/web/styles/*',
            'parrot/web/images/*',
            'parrot/web/scripts/*'],
        'configs': [
            'parrot/pool/configs/*'],
        '': [
            'EPLv1.0.txt',
            'README.md',
            'index.html']
    },
    long_description=open('README.md').read(),
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Simulators"
    ],
)
