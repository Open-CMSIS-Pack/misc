# Copyright 2021 NXP
# All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0

""" Execution of include path estimation and pdsc coverage for specific pack."""

import os
from modules import estimateincludepaths as eip
from modules import pdsccoverage as pcov
pack = r'..\components\ARM.mbedTLS.1.6.0'
eip.estimate_include_paths(pack)
pcov.pdsc_coverage(pack)
