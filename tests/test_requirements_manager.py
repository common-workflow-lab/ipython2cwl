import shutil
import sys
import uuid
from unittest import TestCase

from ipython2cwl.requirements_manager import RequirementsManager
import subprocess
import os


class TestRequirementsManager(TestCase):
    here = os.path.abspath(os.path.dirname(__file__))
    maxDiff = None

    @classmethod
    def tearDownClass(cls):
        venvs_to_delete = [venv for venv in os.listdir(cls.here) if venv.startswith('venv_') and os.path.isdir(os.sep.join([cls.here, venv]))]
        for venv in venvs_to_delete:
            venv = os.sep.join([cls.here, venv])
            print(f'Deleting venv: {venv}')
            shutil.rmtree(venv)

    def test_get_all(self):
        requirements = RequirementsManager.get_all()
        requirements_without_version = [r.split('==')[0] for r in requirements]
        self.assertIn('nbformat', requirements_without_version)
        self.assertNotIn('ipython2cwl', requirements_without_version)
        venv_name = os.sep.join([f'venv_{str(uuid.uuid4())}'])
        venv_python = os.sep.join([venv_name, 'bin', 'python'])
        create_venv_command = [sys.executable, "-m", "virtualenv", venv_name]
        print(' '.join(create_venv_command), 'in directory', self.here)
        proc = subprocess.run(
            create_venv_command,
            cwd=self.here,
            check=True
        )
        requirements_install_command = [venv_python, '-m', 'pip', 'install', *requirements]
        print('install requirements:', ' '.join(requirements_install_command))
        proc = subprocess.run(
            requirements_install_command,
            cwd=self.here,
            check=True,
            env={},
        )
        shutil.rmtree(venv_name)
