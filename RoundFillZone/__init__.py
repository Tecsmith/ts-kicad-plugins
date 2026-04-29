# Copyright 2026 Silvino R. (@silvinor)
# SPDX-License-Identifier: MIT

from __future__ import print_function
import pprint
import traceback
import sys

print("Starting plugin RoundFillZone")
try:
    from .RoundFillZone import *
    RoundFillZone().register()
except Exception as e:
    traceback.print_exc(file=sys.stdout)
    pprint.pprint(e)
