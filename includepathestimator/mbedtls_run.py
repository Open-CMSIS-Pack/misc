import os
from modules import estimateincludepaths as eip
from modules import pdsccoverage as pcov
eip.estimate_include_paths(r'c:\GIT_shadowfax\misc\components\ARM.mbedTLS.1.6.0')
pcov.pdsc_coverage(r'c:\GIT_shadowfax\misc\components\ARM.mbedTLS.1.6.0')
