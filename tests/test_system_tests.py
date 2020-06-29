import os
import shutil
import tempfile
from subprocess import DEVNULL
from unittest import TestCase

import cwltool.factory
import pkg_resources
import yaml
from cwltool.context import RuntimeContext


class TestConsoleScripts(TestCase):
    maxDiff = None
    here = os.path.abspath(os.path.dirname(__file__))
    repo_like_dir = os.path.join(here, 'repo-like')

    def test_repo2cwl(self):
        output_dir = tempfile.mkdtemp()
        print(f'output directory:\t{output_dir}')
        repo2cwl = pkg_resources.load_entry_point('ipython2cwl', 'console_scripts', 'jupyter-repo2cwl')
        self.assertEqual(
            0,
            repo2cwl(['-o', output_dir, self.repo_like_dir])
        )
        self.assertListEqual(['example1.cwl'], [f for f in os.listdir(output_dir) if not f.startswith('.')])

        with open(os.path.join(output_dir, 'example1.cwl')) as f:
            print(20 * '=')
            print('workflow file')
            print(f.read())
            print(20 * '=')

        runtime_context = RuntimeContext()
        runtime_context.outdir = output_dir
        runtime_context.basedir = output_dir
        runtime_context.default_stdout = DEVNULL
        runtime_context.default_stderr = DEVNULL
        fac = cwltool.factory.Factory(runtime_context=runtime_context)

        example1_tool = fac.make(os.path.join(output_dir, 'example1.cwl'))
        result = example1_tool(
            datafilename={'class': 'File', 'location': os.path.join(self.repo_like_dir, 'data.yaml')})
        with open(result['results_filename']['location'][7:]) as f:
            new_data = yaml.safe_load(f)
        self.assertDictEqual({'entry1': 2, 'entry2': 'foo', 'entry3': 'bar'}, new_data)
        shutil.rmtree(output_dir)
