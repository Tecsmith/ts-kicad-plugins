#!/bin/sh

if [ -z "$1" ]; then
  VERSION="v0.0.0"
else
  VERSION="$1"
fi

echo "Clean up old files"
rm -f pcm/*.zip
rm -rf pcm/archive

echo "Create folder structure for ZIP"
mkdir -p pcm/archive/resources

echo "Copy files to destination"
# cp VERSION pcm/archive
cp -r plugins pcm/archive
cp resources/icon.png pcm/archive/resources/icon.png
cp pcm/metadata.template.json pcm/archive/metadata.json

echo "Write version info to file"
echo "$VERSION" > pcm/archive/VERSION

echo "Modify archive metadata.json"
sed -i "s/VERSION_HERE/$VERSION/g" pcm/archive/metadata.json
sed -i -E '/\"kicad_version\": \"[0-9]+\.[0-9]\",/ s/.$//g' pcm/archive/metadata.json
sed -i "/SHA256_HERE/d" pcm/archive/metadata.json
sed -i "/DOWNLOAD_SIZE_HERE/d" pcm/archive/metadata.json
sed -i "/DOWNLOAD_URL_HERE/d" pcm/archive/metadata.json
sed -i "/INSTALL_SIZE_HERE/d" pcm/archive/metadata.json

echo "Zip PCM archive"
cd pcm/archive
zip -r ../kicad-pcm-"$VERSION".zip .
cd ../..

echo "Gather data for repo rebuild"
echo VERSION=$VERSION >> "$GITHUB_ENV"
echo DOWNLOAD_SHA256=$(shasum --algorithm 256 pcm/kicad-pcm-"$VERSION".zip | xargs | cut -d' ' -f1) >> "$GITHUB_ENV"
echo DOWNLOAD_SIZE=$(ls -l pcm/kicad-pcm-"$VERSION".zip | xargs | cut -d' ' -f5) >> "$GITHUB_ENV"
echo DOWNLOAD_URL="https:\/\/github.com\/tecsmith\/ts-kicad-plugins\/releases\/download\/$VERSION\/kicad-pcm-$VERSION.zip" >> "$GITHUB_ENV"
echo INSTALL_SIZE=$(unzip -l pcm/kicad-pcm-"$VERSION".zip | tail -1 | xargs | cut -d' ' -f1) >> "$GITHUB_ENV"
echo KICAD_VERSION=$(grep -oP '(?<="kicad_version": ")[^"]*' pcm/metadata.template.json) >> "$GITHUB_ENV"
echo PROJECT_NAME=$(grep name pcm/metadata.template.json | head -1 | grep -oP '(?<="name": ")[^"]*') >> "$GITHUB_ENV"
