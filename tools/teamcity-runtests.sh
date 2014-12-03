#!/bin/bash
#
# This script assumes that the project 'ptyprocess' is
# available in the parent of the project's folder.
set -e
set -o pipefail

here=$(cd `dirname $0`; pwd)
osrel=$(uname -s)

# run tests
cd $here/..
ret=0
tox || ret=$?

if [ $ret -ne 0 ]; then
	# we always exit 0, preferring instead the jUnit XML
	# results to be the dominate cause of a failed build.
	echo "py.test returned exit code ${ret}." >&2
	echo "the build should detect and report these failing tests." >&2
fi

# combine all coverage to single file, publish as build
# artifact in {pexpect_projdir}/build-output
mkdir -p build-output
coverage combine
mv .coverage build-output/.coverage.${osrel}.$RANDOM.$$
