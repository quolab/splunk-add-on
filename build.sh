#!/bin/bash
set -e

APP="TA-quolab"
BUILD="build/$APP"

VER=$(git describe --abbrev=4 --tags --dirty --match='v*' ||
      grep version default/app.conf | cut -f2 -d=)
VER=${VER/[v ]/}
TARBALL=${APP/-/_}-${VER}.tgz

[[ -d "$BUILD" ]] && rm -rf "$BUILD"
mkdir -p "$BUILD"
mkdir -p "$BUILD/lib"

echo "Building QuoLab add-on for Splunk ${VER}"
### DEVELOPER INPUT NEEDED.  You must add all the relevant files/directories here:
# appserver lookups
cp -a bin default metadata static README.md README "$BUILD"
python -m pip install --isolated --disable-pip-version-check -r requirements.txt -t "$BUILD/lib"
find "$BUILD/lib" "$BUILD/bin" \( -name '*.py[co]' -o -name '__pycache__' -o -name '*.log*' \) -delete
rm -rf $BUILD/lib/bin $BUILD/lib/*.{dist,egg}-info

find "$BUILD" -name '.DS_Store' -delete

echo "Exporting to $TARBALL"
[[ -d "dist" ]] || mkdir dist

# MAC OSX undocumented hack to prevent creation of '._*' folders
export COPYFILE_DISABLE=1

(
cd build
tar -czvf "../dist/$TARBALL" "$APP"
)
echo "dist/$TARBALL" > .latest_release
