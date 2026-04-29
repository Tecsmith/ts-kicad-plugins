# Copyright 2026 Silvino R. (@silvinor)
# SPDX-License-Identifier: MIT

from __future__ import print_function
import pprint
import traceback
import sys

print("Starting plugin RoundZoneRule")
try:
    from .RoundZoneRule import *
    RoundZoneRule().register()
except Exception as e:
    traceback.print_exc(file=sys.stdout)
    pprint.pprint(e)
