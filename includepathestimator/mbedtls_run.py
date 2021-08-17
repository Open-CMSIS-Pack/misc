import os
from modules import estimateincludepaths as eip
from modules import pdsccoverage as pcov
pack = r'..\components\ARM.mbedTLS.1.6.0'
eip.estimate_include_paths(pack)
pcov.pdsc_coverage(pack)
