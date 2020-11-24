#!/bin/bash

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DOCU_MAKE_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

rm -rf "${DOCU_MAKE_DIR}/pycity_scheduling.*.rst"
sphinx-apidoc -F -H "pycity_scheduling" -o "${DOCU_MAKE_DIR}" "${DOCU_MAKE_DIR}/../../src/pycity_scheduling"
make -C "${DOCU_MAKE_DIR}" clean
make -C "${DOCU_MAKE_DIR}" html
