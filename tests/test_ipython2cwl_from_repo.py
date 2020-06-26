import os
import shutil
import tempfile
from unittest import TestCase

import docker
from git import Repo

from ipython2cwl.repo2cwl import repo2cwl


class Test2CWLFromRepo(TestCase):
    maxDiff = None
    here = os.path.abspath(os.path.dirname(__file__))

    def test_docker_build(self):
        # TODO: test with jn with same name
        # setup a simple git repo
        git_dir = tempfile.mkdtemp()
        jn_repo = Repo.init(git_dir)
        shutil.copy(
            os.path.join(self.here, 'simple.ipynb'),
            os.path.join(git_dir, 'simple.ipynb'),
        )
        jn_repo.index.add('simple.ipynb')
        jn_repo.index.commit("initial commit")

        print(git_dir)

        dockerfile_image_id, cwl_tool = repo2cwl(jn_repo)
        self.assertEqual(1, len(cwl_tool))
        docker_client = docker.from_env()
        script = docker_client.containers.run(dockerfile_image_id, 'cat /app/cwl/bin/simple')
        self.assertIn('fig.figure.savefig(after_transform_data)', script.decode())
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': '/cwl/bin/simple',
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
