rm pycity_scheduling.*.rst
sphinx-apidoc -F -H "pycity_scheduling" -o "." "../pycity_scheduling"
make clean
make html