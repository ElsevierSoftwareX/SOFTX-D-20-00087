FROM python:3.6 AS base

ENV GUROBI_HOME="/opt/gurobi900/linux64"

ENV PATH="${PATH}:$GUROBI_HOME/bin" \
    LD_LIBRARY_PATH="/usr/local/lib:/usr/local/lib64:$GUROBI_HOME/lib"

## add gurobi 9.0.0
RUN curl https://packages.gurobi.com/9.0/gurobi9.0.0_linux64.tar.gz > /gurobi.tar.gz &&\
    tar xfz gurobi.tar.gz -C /opt/ &&\
    chmod 777 -R $GUROBI_HOME &&\
    rm gurobi.tar.gz &&\
    rm -r $GUROBI_HOME/docs &&\
    rm -r $GUROBI_HOME/examples &&\
    cd $GUROBI_HOME &&\
    python3 setup.py install &&\
    cd /

# add richardsonpy
#  Currently the pyPI version of richardsonpy seems broken
#  As a workaround richardsonpy is downloaded from github and -e is used for pip

# determine if cache is usable
ADD https://api.github.com/repos/RWTH-EBC/richardsonpy/git/refs/heads/master /dev/null

# download, install and test richardsonpy
RUN git clone --depth=1 https://github.com/RWTH-EBC/richardsonpy &&\
    pip3 install --no-cache-dir -e richardsonpy/ &&\
    pip3 install --no-cache-dir pytest &&\
    pytest -q richardsonpy/

# add pyCity
#  Currently the pyPI version of pyCity seems broken
#  As a workaround pycity is downloaded from github and -e is used for pip

# determine if cache is usable
ADD https://api.github.com/repos/RWTH-EBC/richardsonpy/git/refs/heads/master /dev/null
# download, install and test pyCity
RUN git clone --depth=1 https://github.com/RWTH-EBC/pyCity &&\
    pip3 install --no-cache-dir -e pyCity/ &&\
    pytest -q pyCity/

ENTRYPOINT /bin/bash

FROM base AS lint
RUN pip3 install --no-cache-dir pylint

FROM base
COPY . /pyCity_scheduling
RUN pip3 install --no-cache-dir /pyCity_scheduling[test]
