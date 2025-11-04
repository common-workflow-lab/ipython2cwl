import os
import shutil
from unittest import TestCase

from ipython2cwl.requirements_manager import RequirementsManager


class TestRequirementsManager(TestCase):
    here = os.path.abspath(os.path.dirname(__file__))
    maxDiff = None

    @classmethod
    def tearDownClass(cls):
        venvs_to_delete = [
            venv
            for venv in os.listdir(cls.here)
            if venv.startswith('venv_') and os.path.isdir(os.sep.join([cls.here, venv]))
        ]
        for venv in venvs_to_delete:
            venv = os.sep.join([cls.here, venv])
            print(f'Deleting venv: {venv}')
            shutil.rmtree(venv)

    def test_get_all(self):
        requirements = RequirementsManager.get_all()
        requirements_without_version = [r.split('==')[0] for r in requirements]
        self.assertIn('nbformat', requirements_without_version)
        self.assertNotIn('ipython2cwl', requirements_without_version)
