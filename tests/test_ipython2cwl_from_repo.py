import os
import shutil
import tempfile
from io import StringIO
from unittest import TestCase, skipIf

import docker
import yaml
from git import Repo

from ipython2cwl.repo2cwl import repo2cwl


class Test2CWLFromRepo(TestCase):
    maxDiff = None
    here = os.path.abspath(os.path.dirname(__file__))

    @skipIf("TRAVIS_IGNORE_DOCKER" in os.environ and os.environ["TRAVIS_IGNORE_DOCKER"] == "true",
            "Skipping this test on Travis CI.")
    def test_docker_build(self):
        # TODO: test with jn with same name
        # TODO: test having notebooks without typing annotations
        # TODO: should I execute cwltool??
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

        dockerfile_image_id, cwl_tool = repo2cwl(jn_repo)
        self.assertEqual(1, len(cwl_tool))
        docker_client = docker.from_env()
        script = docker_client.containers.run(dockerfile_image_id, '/app/cwl/bin/simple', entrypoint='/bin/cat')
        self.assertIn('fig.figure.savefig(after_transform_data)', script.decode())
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': '/app/cwl/bin/simple',
                'hints': {
                    'DockerRequirement': {'dockerImageId': dockerfile_image_id}
                },
                'inputs': {
                    'dataset': {
                        'type': 'File',
                        'inputBinding': {
                            'prefix': '--dataset'
                        }
                    }
                },
                'outputs': {
                    'original_image': {
                        'type': 'File',
                        'outputBinding': {
                            'glob': 'original_data.png'
                        }
                    },
                    'after_transform_data': {
                        'type': 'File',
                        'outputBinding': {
                            'glob': 'new_data.png'
                        }
                    }
                },
            },
            cwl_tool[0]
        )
        cwl = StringIO()
        yaml.safe_dump(cwl_tool[0], cwl)
        cwl_code = cwl.getvalue()
        print(cwl_code)
