from setuptools import setup, find_packages

setup(
    name='pyCity_scheduling',
    version='0.1',
    author='Institute for Automation of Complex Power Systems'
           'E.ON Energy Research Center, RWTH Aachen University',
    packages=find_packages(),
    package_data={'pycity_scheduling': ['data/*.txt']},
    install_requires=[
        'pyomo',
        'numpy>=1.13.3,<1.14.0',
        'pycity_base>=0.2.1',
        'Shapely>=1.6.4'
    ],
    extras_require={
        'test': ['gurobipy>=5.7.2']
    },
    platforms='any',
    classifiers=[
        "Development Status :: 3 - Alpha"
        "Intended Audience :: Science/Research"
        "Topic :: Scientific/Engineering"
        "Natural Language :: English"
        "Programming Language :: Python :: 3.6"
    ],
    zip_safe=False
)
