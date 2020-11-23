#!/bin/bash

rm pycity_scheduling.*.rst
sphinx-apidoc -F -H "pycity_scheduling" -o "." "../../src/pycity_scheduling"
make clean
make html