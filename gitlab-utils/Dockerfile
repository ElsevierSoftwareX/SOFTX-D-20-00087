# The pycity_scheduling framework's Dockerfile to be used by the Gitlab-CI.
# Download, build, and install all required base packages and then setup the pycity_scheduling framework environment.


FROM archlinux:latest AS base


ENTRYPOINT /bin/bash


# Install the archlinux base packages:
RUN pacman -Syu sudo git patch wget php doxygen make cmake clang base-devel gcc gcc-fortran unzip tar bzip2 expat gdbm libffi openssl bluez-libs mpdecimal sqlite tk bison flex pkgconf boost boost-libs zlib gmp blas gsl readline ncurses cliquer ghc ghc-libs haskell-criterion coin-or-asl lapack metis --noconfirm

# Scipopt cannot be build with tbb >= 2021
RUN pacman -U https://archive.archlinux.org/packages/t/tbb/tbb-2020.3-1-x86_64.pkg.tar.zst --noconfirm

ENV CMAKE_BUILD_PARALLEL_LEVEL="8"
ENV MAKEFLAGS "-j8"

# Create a builduser (required for some archlinux operations running inside Docker):
RUN useradd builduser -m -d /home/builduser &&\
    passwd -d builduser &&\
    printf 'builduser ALL=(ALL) ALL\n' | tee a /etc/sudoers &&\
    printf 'root ALL=(ALL) ALL\n' | tee a /etc/sudoers


# Download and install the required IPOPT solver (version 3.13.2):
RUN cd / &&\
    sudo --preserve-env=MAKEFLAGS,CMAKE_BUILD_PARALLEL_LEVEL -u builduser /bin/bash -c 'mkdir -p ~/coin-or-coinmumps && cd ~/coin-or-coinmumps && wget --quiet "https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=coin-or-coinmumps&id=43e3a59117757bb582f52c041b64a741fa19324b" -O PKGBUILD && makepkg -s' &&\
    cd /home/builduser/coin-or-coinmumps &&\
    pacman -U *.pkg.tar.zst --noconfirm &&\
    sudo --preserve-env=MAKEFLAGS,CMAKE_BUILD_PARALLEL_LEVEL -u builduser /bin/bash -c 'mkdir -p ~/coin-or-ipopt && cd ~/coin-or-ipopt && wget --quiet "https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=coin-or-ipopt&id=7e213d37212b3c9f2658a7608bf4c0289a8a7319" -O PKGBUILD && makepkg -s' &&\
    cd /home/builduser/coin-or-ipopt &&\
    pacman -U *.pkg.tar.zst --noconfirm &&\
    cd /


# Download the required HiGHS LP solver source code:
RUN mkdir -p /opt/HiGHS
ENV HiGHS_BASE_DIR="/opt/HiGHS"

RUN cd $HiGHS_BASE_DIR &&\
    git clone --depth 1 https://github.com/ERGO-Code/HiGHS.git &&\
    cd /


# Download the required hMETIS binary:
RUN mkdir -p /opt/hMETIS
ENV HMETIS_BASE_DIR="/opt/hMETIS"

RUN cd $HMETIS_BASE_DIR &&\
    wget --quiet http://glaros.dtc.umn.edu/gkhome/fetch/sw/hmetis/hmetis-1.5-linux.tar.gz &&\
    tar xzf $HMETIS_BASE_DIR/hmetis-1.5-linux.tar.gz &&\
    chmod +x $HMETIS_BASE_DIR/hmetis-1.5-linux/hmetis &&\
	rm -rf $HMETIS_BASE_DIR/hmetis-1.5-linux.tar.gz &&\
    cd /

ENV PATH="${PATH}:$HMETIS_BASE_DIR/hmetis-1.5-linux/"


# Download, patch and build bliss-0.73p (as a recommended bugfix for the SCIP solver):
RUN mkdir -p /opt/bliss
ENV BLISS_BASE_DIR="/opt/bliss"

RUN cd $BLISS_BASE_DIR &&\
    wget --quiet https://www3.hhu.de/stups/buildlibs/bliss-0.73.zip &&\
    unzip $BLISS_BASE_DIR/bliss-0.73.zip &&\
	rm -rf $BLISS_BASE_DIR/bliss-0.73.zip &&\
    wget --quiet https://www.scipopt.org/download/bugfixes/scip-7.0.0/bliss-0.73.patch &&\
    patch -l -p0 < bliss-0.73.patch &&\
    mv $BLISS_BASE_DIR/bliss-0.73 $BLISS_BASE_DIR/bliss-0.73p &&\
    cd $BLISS_BASE_DIR/bliss-0.73p &&\
    sed -i -e '31s/0.73/0.73p/g' ./defs.hh &&\
    make lib_gmp bliss_gmp &&\
    cd /


ENV PATH="${PATH}:$BLISS_BASE_DIR/bliss-0.73p/"


# Download, build and install the SCIP optimization solver (SCIPOptSuite 7.0.3).
# Important note: You are allowed to retrieve a copy of SCIP for research purposes as a member of a noncommercial and academic institution only.
# To get a copy of SCIP, you need to certify that you are a member of a noncommercial, academic institution and accept the ZIB Academic License.
# Commercial use requires a commercial license.
# For further information visit: https://scipopt.org/#scipoptsuite
RUN mkdir -p /opt/scip
ENV SCIPAMPL_BASE_DIR="/opt/scip"

RUN pacman -Qe

RUN cd $SCIPAMPL_BASE_DIR &&\
    wget --quiet https://www.scipopt.org/download/release/scipoptsuite-7.0.3.tgz &&\
    tar xzf $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3.tgz &&\
	rm -rf $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3.tgz &&\
    cd /

RUN cd $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3 &&\
    mkdir -p $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/build &&\
    cd $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/build &&\
    cmake .. -DCMAKE_BUILD_TYPE=Release -DBLISS_DIR=$BLISS_BASE_DIR/bliss-0.73p -DBOOST=on -DGCG=on -DGMP=on -DGSL=on -DHIGHS=on -DHIGHS_DIR=$HiGHS_BASE_DIR/HiGHS -DHMETIS=on -DIPOPT=on -DLPS=spx -DPAPILO=on -DQUADMATH=on -DREADLINE=on -DSCIP=on -DSHARED=on -DSOPLEX=on -DSYM=bliss -DWORHP=off -DZIMPL=on -DZLIB=on &&\
    make &&\
    cd /
ENV SCIP_DIR=$SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/build

RUN cd $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/scip/interfaces/ampl &&\
    ./get.ASL &&\
    cd $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/scip/interfaces/ampl/solvers &&\
    sh configurehere &&\
    make -f makefile.u &&\
    cd /

RUN cd $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/scip/interfaces/ampl &&\
    mkdir -p $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/scip/interfaces/ampl/build &&\
    cd $SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/scip/interfaces/ampl/build &&\
    cmake .. -DSCIP_DIR=$SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/build &&\
    make &&\
    cd /

ENV PATH="${PATH}:$SCIPAMPL_BASE_DIR/scipoptsuite-7.0.3/scip/interfaces/ampl/build"


# Download, build and install the Gurobi optimization solver (Gurobi 9.1.2).
# Important note: You are allowed to retrieve a copy of Gurobi for research purposes as a member of a non-commercial and academic institution only.
# To get a copy of Gurobi, you need to request for an academic license at Gurobi Optimization, LLC.
# Commercial use requires a commercial license.
# For further information visit: https://www.gurobi.com/
RUN mkdir -p /opt/gurobi
ENV GUROBI_BASE_DIR="/opt/gurobi"
ENV GUROBI_HOME="${GUROBI_BASE_DIR}/gurobi912/linux64"

RUN cd $GUROBI_BASE_DIR &&\
    wget --quiet https://packages.gurobi.com/9.1/gurobi9.1.2_linux64.tar.gz &&\
    tar xfz gurobi9.1.2_linux64.tar.gz &&\
    rm $GUROBI_BASE_DIR/gurobi9.1.2_linux64.tar.gz &&\
	chmod -R 755 $GUROBI_BASE_DIR/gurobi912 &&\
    cd /

ENV PATH="${PATH}:$GUROBI_HOME/bin"
ENV LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:$GUROBI_HOME/lib"

FROM base as python37

# Install Python version 3.7 together with some core package:
RUN cd / &&\
    sudo -u builduser /bin/bash -c 'mkdir -p ~/python37 && cd ~/python37 && curl -L -O https://aur.archlinux.org/cgit/aur.git/snapshot/python37.tar.gz' &&\
    sudo -u builduser /bin/bash -c 'gpg --keyserver keyserver.ubuntu.com --recv-keys 0D96DF4D4110E5C43FBFB17F2D347EA6AA65421D' &&\
    sudo --preserve-env=MAKEFLAGS,CMAKE_BUILD_PARALLEL_LEVEL -u builduser /bin/bash -c 'cd ~/python37 && tar -xf python37.tar.gz && cd python37 && makepkg -s' &&\
    cd /home/builduser/python37/python37 &&\
    pacman -U *.pkg.tar.zst --noconfirm &&\
    ln -s /usr/sbin/python3.7 /usr/sbin/python3 &&\
    wget --quiet https://bootstrap.pypa.io/get-pip.py &&\
    python3.7 get-pip.py &&\
    python3.7 -m pip install --upgrade pip &&\
    python3.7 -m pip install setuptools wheel twine pytest &&\
    cd /



RUN cd $GUROBI_HOME &&\
    python3.7 setup.py install &&\
    cd /

# Add requirements to docker image
ADD requirements.txt /

RUN pip install --no-cache-dir -r /requirements.txt

FROM base as python38

# Install Python version 3.8 together with some core package:
RUN cd / &&\
    sudo -u builduser /bin/bash -c 'mkdir -p ~/python38 && cd ~/python38 && curl -L -O https://aur.archlinux.org/cgit/aur.git/snapshot/python38.tar.gz' &&\
    sudo -u builduser /bin/bash -c 'gpg --keyserver keyserver.ubuntu.com --recv-keys E3FF2839C048B25C084DEBE9B26995E310250568' &&\
    sudo --preserve-env=MAKEFLAGS,CMAKE_BUILD_PARALLEL_LEVEL -u builduser /bin/bash -c 'cd ~/python38 && tar -xf python38.tar.gz && cd python38 && makepkg -s' &&\
    cd /home/builduser/python38/python38 &&\
    pacman -U *.pkg.tar.zst --noconfirm &&\
    ln -s /usr/sbin/python3.8 /usr/sbin/python3 &&\
    wget --quiet https://bootstrap.pypa.io/get-pip.py &&\
    python3.8 get-pip.py &&\
    python3.8 -m pip install --upgrade pip &&\
    python3.8 -m pip install setuptools wheel twine pytest &&\
    cd /



RUN cd $GUROBI_HOME &&\
    python3.8 setup.py install &&\
    cd /

# Add requirements to docker image
ADD requirements.txt /

RUN pip install --no-cache-dir -r /requirements.txt

FROM base as python39

# Install Python version 3.9 together with some core package:
RUN cd / &&\
    pacman -U https://archive.archlinux.org/packages/p/python/python-3.9.9-1-x86_64.pkg.tar.zst --noconfirm &&\
    wget --quiet https://bootstrap.pypa.io/get-pip.py &&\
    python3.9 get-pip.py &&\
    python3.9 -m pip install --upgrade pip &&\
    python3.9 -m pip install setuptools wheel twine pytest &&\
    cd /



RUN cd $GUROBI_HOME &&\
    python3.9 setup.py install &&\
    cd /

# Add requirements to docker image
ADD requirements.txt /

RUN pip install --no-cache-dir -r /requirements.txt