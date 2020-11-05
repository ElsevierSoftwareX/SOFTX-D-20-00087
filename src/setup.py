"""
:::::::::::::::::::::::::::::::::::::::
::: The pycity_scheduling Framework :::
:::::::::::::::::::::::::::::::::::::::


Institution:
::::::::::::
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors:
::::::::
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


from setuptools import setup, find_packages


setup(
    name='pycity_scheduling',
    description='A Python framework for the development and assessment of optimisation-based power scheduling'
                'algorithms for multi-energy systems in city districts',
    version='0.9',
    author='Sebastian Schwarz, Sebastian Alexander Uerlich, Antonello Monti'
           'Institute for Automation of Complex Power Systems'
           'E.ON Energy Research Center, RWTH Aachen University',
    author_email='post_acs@eonerc.rwth-aachen.de',
    url='https://www.acs.eonerc.rwth-aachen.de/cms/~dlkd/E-ON-ERC-ACS/',
    license='MIT',
    license_file='LICENSE.txt',
    packages=find_packages(),
    package_data={'pycity_scheduling': ['data/*.txt']},
    install_requires=[
        'pyomo',
        'numpy',
        'pandas',
        'matplotlib',
        'pycity_base>=0.3.1',
        'Shapely>=1.6.4'
    ],
    extras_require={
        'test': ['pytest']
    },
    platforms='any',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Scientists/Engineers/Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Science/Engineering",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
    ],
    zip_safe=False
)
