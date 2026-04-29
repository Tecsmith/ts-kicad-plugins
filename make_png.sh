#!/bin/bash

magick -background none RoundFillZone/RoundFillZone.svg -resize 32x32 RoundFillZone/RoundFillZone.png
magick -background none RoundFillZone/RoundFillZone.dark.svg -resize 32x32 RoundFillZone/RoundFillZone.dark.png

magick -background none RoundZoneRule/RoundZoneRule.svg -resize 32x32 RoundZoneRule/RoundZoneRule.png
magick -background none RoundZoneRule/RoundZoneRule.dark.svg -resize 32x32 RoundZoneRule/RoundZoneRule.dark.png
