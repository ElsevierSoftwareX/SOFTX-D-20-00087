"""
The pycity_scheduling framework


Institution
-----------
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors
-------
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import unittest
import os
from importlib.machinery import SourceFileLoader


class TestExamples(unittest.TestCase):
    def setUp(self):
        this_dir = os.path.dirname(__file__)
        self.example_dir = os.path.join(this_dir, "../../examples")
        self.files = os.listdir(self.example_dir)
        if len(self.files) == 0:
            self.skipTest("No example files found.")
        return

    def test_all_examples(self):
        for file in self.files:
            filepath = os.path.join(self.example_dir, file)
            example_name, file_ext = os.path.splitext(os.path.split(filepath)[-1])
            if file_ext.lower() == '.py':
                example_module = SourceFileLoader('main', filepath).load_module()
                example_module.main(do_plot=False)
        return
