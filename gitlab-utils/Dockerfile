# The pycity_scheduling framework's Dockerfile to be used by the Gitlab-CI.
# Download, build, and install all required base packages and then setup the pycity_scheduling framework environment.


FROM archlinux:latest AS base


ENTRYPOINT /bin/bash


# Install the archlinux base packages:
RUN pacman -Syu sudo git patch wget php doxygen make cmake clang base-devel gcc gcc-fortran unzip tar bzip2 expat gdbm libffi openssl bluez-libs mpdecimal sqlite tk bison flex pkgconf boost boost-libs zlib gmp blas gsl readline ncurses tbb cliquer ghc ghc-libs haskell-criterion coin-or-asl lapack metis --noconfirm


# Create a builduser (required for some archlinux operations running inside Docker):
RUN useradd builduser -m -d /home/builduser &&\
    passwd -d builduser &&\
    printf 'builduser ALL=(ALL) ALL\n' | tee a /etc/sudoers &&\
    printf 'root ALL=(ALL) ALL\n' | tee a /etc/sudoers


# Install Python version 3.6 together with some core package:
RUN cd / &&\
    sudo -u builduser /bin/bash -c 'mkdir -p ~/python36 && cd ~/python36 && wget --quiet "https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=python36&id=a057b43d348f307a04e166cbef04deec7cf4c8c4" -O PKGBUILD && makepkg -s' &&\
    cd /home/builduser/python36 &&\
    pacman -U *.pkg.tar.zst --noconfirm &&\
    wget --quiet https://bootstrap.pypa.io/get-pip.py &&\
    python3.6 get-pip.py &&\
    python3.6 -m pip install --upgrade pip &&\
    python3.6 -m pip install setuptools wheel twine pytest &&\
    cd /


# Download and install the required IPOPT solver (version 3.13.2):
RUN cd / &&\
    sudo -u builduser /bin/bash -c 'mkdir -p ~/coin-or-coinmumps && cd ~/coin-or-coinmumps && wget --quiet "https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=coin-or-coinmumps&id=43e3a59117757bb582f52c041b64a741fa19324b" -O PKGBUILD && makepkg -s' &&\
    cd /home/builduser/coin-or-coinmumps &&\
    pacman -U *.pkg.tar.zst --noconfirm &&\
    sudo -u builduser /bin/bash -c 'mkdir -p ~/coin-or-ipopt && cd ~/coin-or-ipopt && wget --quiet "https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=coin-or-ipopt&id=7e213d37212b3c9f2658a7608bf4c0289a8a7319" -O PKGBUILD && makepkg -s' &&\
    cd /home/builduser/coin-or-ipopt &&\
    pacman -U *.pkg.tar.zst --noconfirm &&\
    cd /


# Download the required HiGHS LP solver source code:
RUN mkdir -p /opt/HiGHS
ENV HiGHS_BASE_DIR="/opt/HiGHS"

RUN cd $HiGHS_BASE_DIR &&\
    git clone https://github.com/ERGO-Code/HiGHS.git &&\
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

RUN cd $GUROBI_BASE_DIR &&\
    wget --quiet https://packages.gurobi.com/9.1/gurobi9.1.2_linux64.tar.gz &&\
    tar xfz gurobi9.1.2_linux64.tar.gz &&\
    rm $GUROBI_BASE_DIR/gurobi9.1.2_linux64.tar.gz &&\
	chmod -R 755 $GUROBI_BASE_DIR/gurobi912 &&\
    cd $GUROBI_BASE_DIR/gurobi912/linux64 &&\
    python3.6 setup.py install &&\
    cd /

ENV PATH="${PATH}:$GUROBI_BASE_DIR/gurobi912/linux64/bin"
ENV LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:$GUROBI_BASE_DIR/gurobi912/linux64/lib"


# Download and install Python package richardsonpy:
# Unfortunately, the current PyPI version of package richardsonpy seems to be broken.
# As a workaround, richardsonpy is downloaded from github and flag -e is used for pip.
RUN cd /opt &&\
    git clone --depth=1 -b v0.2.1 https://github.com/RWTH-EBC/richardsonpy &&\
    python3.6 -m pip install --no-cache-dir -e richardsonpy/ &&\
	cd /


# Download and install Python package pycity_base:
# Always use a specific tagged pycity_base version from github.
# Thus, pycity_base is downloaded from github and flag -e is used for pip.
RUN cd /opt &&\
    git clone --depth=1 -b v0.3.2 https://github.com/RWTH-EBC/pyCity pycity_base &&\
    python3.6 -m pip install --no-cache-dir -e pycity_base/ &&\
	cd /


# Download and install the other requirements for package pycity_scheduling:
# Moreover, install the third-party Python site-packages that are required by the used tools during the different CI stages.
RUN python3.6 -m pip install --no-cache-dir importlib pylint sphinx numpydoc
