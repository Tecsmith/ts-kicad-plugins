#!/bin/bash

magick -background none ../plugins/RoundFillZone/RoundFillZone.svg -resize 32x32 ../plugins/RoundFillZone/RoundFillZone.png
magick -background none ../plugins/RoundFillZone/RoundFillZone.dark.svg -resize 32x32 ../plugins/RoundFillZone/RoundFillZone.dark.png

magick -background none ../plugins/RoundZoneRule/RoundZoneRule.svg -resize 32x32 ../plugins/RoundZoneRule/RoundZoneRule.png
magick -background none ../plugins/RoundZoneRule/RoundZoneRule.dark.svg -resize 32x32 ../plugins/RoundZoneRule/RoundZoneRule.dark.png

magick -background none ../plugins/FabText/FabText.svg -resize 32x32 ../plugins/FabText/FabText.png
magick -background none ../plugins/FabText/FabText.dark.svg -resize 32x32 ../plugins/FabText/FabText.dark.png

magick -background none ../plugins/Teardrops/Teardrops.svg -resize 32x32 ../plugins/Teardrops/Teardrops.png
magick -background none ../plugins/Teardrops/Teardrops.dark.svg -resize 32x32 ../plugins/Teardrops/Teardrops.dark.png

magick -background none ../resources/icon.svg -resize 64x64 ../resources/icon.png
