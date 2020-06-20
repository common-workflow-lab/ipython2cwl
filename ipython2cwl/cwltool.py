import ast
import os
import platform
import shutil
import tarfile
import tempfile
from collections import namedtuple
from pathlib import Path
from typing import Dict

import astor
import yaml

from . import iotypes
from .iotypes import CWLFilePathInput
from .requirements_manager import RequirementsManager

with open(os.sep.join([os.path.abspath(os.path.dirname(__file__)), 'template.dockerfile'])) as f:
    DOCKERFILE_TEMPLATE = f.read()
with open(os.sep.join([os.path.abspath(os.path.dirname(__file__)), 'template.setup.py'])) as f:
    SETUP_TEMPLATE = f.read()


# TODO: does not support recursion if main function exists

class AnnotatedVariablesExtractor(ast.NodeTransformer):
    extracted_nodes = []

    def visit_AnnAssign(self, node):
        try:
            if isinstance(node.annotation, ast.Name) and node.annotation.id == CWLFilePathInput.__name__:
                self.extracted_nodes.append((
                    node,
                    'File',
                    'click.Path(exists=True, file_okay=True, dir_okay=False, writable=False, readable=True)',
                    True,
                    True,
                    False,
                ))
                return None
            elif isinstance(node.annotation, ast.Subscript) \
                    and node.annotation.value.id == "Optional" \
                    and node.annotation.slice.value.id == CWLFilePathInput.__name__:
                self.extracted_nodes.append((
                    node,
                    'File?',
                    'click.Path(exists=True, file_okay=True, dir_okay=False, writable=False, readable=True)',
                    False,
                    True,
                    False,
                ))
                return None
        except AttributeError:
            pass
        return node


class AnnotatedIPython2CWLToolConverter:
    """
    That class parses an annotated python script and generates a CWL Command Line Tool
    with the described inputs & outputs.
    """

    _code: str

    _VariableNameTypePair = namedtuple(
        'VariableNameTypePair',
        ['name', 'cwl_typeof', 'click_typeof', 'required', 'is_input', 'is_output']
    )

    """The annotated python code to convert."""

    def __init__(self, annotated_ipython_code: str):
        self._code = annotated_ipython_code
        extractor = AnnotatedVariablesExtractor()
        self._tree = ast.fix_missing_locations(extractor.visit(ast.parse(self._code)))
        self._variables = [
            self._VariableNameTypePair(node.target.id, cwl_type, click_type, required, is_input, is_output)
            for node, cwl_type, click_type, required, is_input, is_output in extractor.extracted_nodes
        ]

    @classmethod
    def _wrap_script_to_method(cls, tree, variables) -> str:
        main_function = ast.parse(os.linesep.join([
            'import click',
            '@click.command()',
            *[f'@click.option("--{variable.name}", type={variable.click_typeof}, required={variable.required})'
              for variable in variables],
            f"def main({','.join([variable.name for variable in variables])}):",
            "\tpass",
            "if __name__ == '__main__':",
            "\tmain()"
        ]))
        main_function.body[1].body = tree.body
        return astor.to_source(main_function)

    def cwl_command_line_tool(self, docker_image_id: str = 'jn2cwl:latest') -> Dict:
        """
        Creates the description of the CWL Command Line Tool.
        :return: The cwl description of the corresponding tool
        """
        inputs = [v for v in self._variables if v.is_input]
        outputs = [v for v in self._variables if v.is_output]

        cwl_tool = {
            'cwlVersion': "v1.1",
            'class': 'CommandLineTool',
            'baseCommand': 'notebookTool',
            'hints': {
                'DockerRequirement': {'dockerImageId': docker_image_id}
            },
            'inputs': {
                input_var.name: {
                    'type': input_var.cwl_typeof,
                    'inputBinding': {
                        'prefix': f'--{input_var.name}'
                    }
                }
                for input_var in inputs},
            'outputs': list(outputs),
        }
        return cwl_tool

    def compile(self, filename: Path = Path('notebookAsCWLTool.tar')) -> str:
        """
        That method generates a tar file which includes the following files:
        main.py - the python script
        tool.cwl - the cwl description file
        Dockerfile - the dockerfile to create the docker image
        :param: filename
        :return: The absolute path of the tar file
        """
        workdir = tempfile.mkdtemp()
        script_path = os.path.join(workdir, 'notebookTool')
        cwl_path = os.path.join(workdir, 'tool.cwl')
        dockerfile_path = os.path.join(workdir, 'Dockerfile')
        setup_path = os.path.join(workdir, 'setup.py')
        requirements_path = os.path.join(workdir, 'requirements.txt')
        with open(script_path, 'wb') as f:
            f.write(self._wrap_script_to_method(self._tree, self._variables).encode())
        with open(cwl_path, 'w') as f:
            yaml.safe_dump(self.cwl_command_line_tool(), f, encoding='utf-8')
        dockerfile = DOCKERFILE_TEMPLATE.format(
            python_version=f'python:{".".join(platform.python_version_tuple())}'
        )
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile)
        with open(setup_path, 'w') as f:
            f.write(SETUP_TEMPLATE)

        with open(requirements_path, 'w') as f:
            f.write(os.linesep.join(RequirementsManager.get_all()))

        with tarfile.open(str(filename.absolute()), 'w') as tar_fd:
            def add_tar(file_to_add): tar_fd.add(file_to_add, arcname=os.path.basename(file_to_add))

            add_tar(script_path)
            add_tar(cwl_path)
            add_tar(dockerfile_path)
            add_tar(setup_path)
            add_tar(requirements_path)

        shutil.rmtree(workdir)
        return str(filename.absolute())
