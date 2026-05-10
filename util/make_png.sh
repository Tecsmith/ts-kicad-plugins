#!/bin/bash

magick -background none ../plugins/RoundFillZone/RoundFillZone.svg -resize 32x32 ../plugins/RoundFillZone/RoundFillZone.png
magick -background none ../plugins/RoundFillZone/RoundFillZone.dark.svg -resize 32x32 ../plugins/RoundFillZone/RoundFillZone.dark.png

magick -background none ../plugins/RoundZoneRule/RoundZoneRule.svg -resize 32x32 ../plugins/RoundZoneRule/RoundZoneRule.png
magick -background none ../plugins/RoundZoneRule/RoundZoneRule.dark.svg -resize 32x32 ../plugins/RoundZoneRule/RoundZoneRule.dark.png

magick -background none ../resources/icon.svg -resize 64x64 ../resources/icon.png
