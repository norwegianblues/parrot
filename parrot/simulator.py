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

from parrot.core import core


def run(config_file, debug=False):
    c = core.Core()

    try:
        c.setup_platform(config_file)
        c.start_nodes()
        c.serve()
    except SystemExit:
        print("\n[Core] User stopped simulation, attempting cleanup")
    finally:
        c.shutdown()
