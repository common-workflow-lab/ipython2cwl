import ast
import os
import shutil
import tempfile
from io import StringIO
from unittest import TestCase, skipIf

import docker
import yaml
from git import Repo

from ipython2cwl.repo2cwl import _repo2cwl


class Test2CWLFromRepo(TestCase):
    maxDiff = None
    here = os.path.abspath(os.path.dirname(__file__))

    @skipIf(
        "TRAVIS_IGNORE_DOCKER" in os.environ
        and os.environ["TRAVIS_IGNORE_DOCKER"] == "true",
        "Skipping this test on Travis CI.",
    )
    def test_docker_build(self):
        # setup a simple git repo
        git_dir = tempfile.mkdtemp()
        jn_repo = Repo.init(git_dir)
        shutil.copy(
            os.path.join(self.here, 'simple.ipynb'),
            os.path.join(git_dir, 'simple.ipynb'),
        )
        with open(os.path.join(git_dir, 'requirements.txt'), 'w') as f:
            f.write('pandas\n')
            f.write('matplotlib\n')
        jn_repo.index.add('simple.ipynb')
        jn_repo.index.add('requirements.txt')
        jn_repo.index.commit("initial commit")

        print(git_dir)

        dockerfile_image_id, cwl_tool = _repo2cwl(jn_repo)
        self.assertEqual(1, len(cwl_tool))
        docker_client = docker.from_env()
        script = docker_client.containers.run(
            dockerfile_image_id, '/app/cwl/bin/simple', entrypoint='/bin/cat'
        )
        self.assertIn('fig.figure.savefig(after_transform_data)', script.decode())
        messages_array_arg_line = ast.parse(
            [
                line.strip()
                for line in script.decode().splitlines()
                if '--messages' in line
            ][-1]
        )
        self.assertEqual(
            '+',  # nargs = '+'
            [
                k.value.s
                for k in messages_array_arg_line.body[0].value.keywords
                if k.arg == 'nargs'
            ][0],
        )
        self.assertEqual(
            'str',  # type = 'str'
            [
                k.value.id
                for k in messages_array_arg_line.body[0].value.keywords
                if k.arg == 'type'
            ][0],
        )

        script_tree = ast.parse(script.decode())
        optional_expression = [
            x
            for x in script_tree.body[-1].body
            if isinstance(x, ast.Expr)
            and isinstance(x.value, ast.Call)
            and len(x.value.args) > 0
            and x.value.args[0].s == '--optional_message'
        ][0]
        self.assertEqual(
            False,
            [
                k.value
                for k in optional_expression.value.keywords
                if k.arg == 'required'
            ][0].value,
        )
        self.assertEqual(
            None,
            [k.value for k in optional_expression.value.keywords if k.arg == 'default'][
                0
            ].value,
        )
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': '/app/cwl/bin/simple',
                'hints': {'DockerRequirement': {'dockerImageId': dockerfile_image_id}},
                'arguments': ['--'],
                'inputs': {
                    'dataset': {
                        'type': 'File',
                        'inputBinding': {'prefix': '--dataset'},
                    },
                    'messages': {
                        'type': 'string[]',
                        'inputBinding': {'prefix': '--messages'},
                    },
                    'optional_message': {
                        'type': 'string?',
                        'inputBinding': {'prefix': '--optional_message'},
                    },
                },
                'outputs': {
                    'original_image': {
                        'type': 'File',
                        'outputBinding': {'glob': 'original_data.png'},
                    },
                    'after_transform_data': {
                        'type': 'File',
                        'outputBinding': {'glob': 'new_data.png'},
                    },
                },
            },
            cwl_tool[0],
        )
        cwl = StringIO()
        yaml.safe_dump(cwl_tool[0], cwl)
        cwl_code = cwl.getvalue()
        print(cwl_code)

        # test for non-annotated jn
        shutil.copy(
            os.path.join(self.here, 'non-annotated.ipynb'),
            os.path.join(git_dir, 'non-annotated.ipynb'),
        )
        jn_repo.index.add("non-annotated.ipynb")
        jn_repo.index.commit("add non annotated notebook")
        dockerfile_image_id, new_cwl_tool = _repo2cwl(jn_repo)
        self.assertEqual(1, len(new_cwl_tool))
        cwl_tool[0]['hints']['DockerRequirement'].pop('dockerImageId')
        new_cwl_tool[0]['hints']['DockerRequirement'].pop('dockerImageId')
        self.assertListEqual(cwl_tool, new_cwl_tool)

        # test with jn with same name in different directory
        os.makedirs(os.path.join(git_dir, 'subdir'), exist_ok=True)
        shutil.copy(
            os.path.join(self.here, 'simple.ipynb'),
            os.path.join(git_dir, 'subdir', 'simple.ipynb'),
        )
        jn_repo.index.add("subdir/simple.ipynb")
        jn_repo.index.commit("add second jn with the same name")
        dockerfile_image_id, new_cwl_tool = _repo2cwl(jn_repo)
        base_commands = [tool['baseCommand'] for tool in new_cwl_tool]
        base_commands.sort()
        self.assertListEqual(
            base_commands, ['/app/cwl/bin/simple', '/app/cwl/bin/subdir/simple']
        )
        script = docker_client.containers.run(
            dockerfile_image_id, '/app/cwl/bin/subdir/simple', entrypoint='/bin/cat'
        )
        self.assertIn('fig.figure.savefig(after_transform_data)', script.decode())
