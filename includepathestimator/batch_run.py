# Copyright 2021 NXP
# All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0

""" Batch analysis of all extracted cmsis packs in components folder."""

import os
from modules import estimateincludepaths as eip
from modules import pdsccoverage as pcov

location = r'..\components'
subfolders = [f.path for f in os.scandir(location) if f.is_dir()]
print(subfolders)
for f in subfolders:
    print("Analyzing folder:", f)
    eip.estimate_include_paths(f)
    pcov.pdsc_coverage(f)
