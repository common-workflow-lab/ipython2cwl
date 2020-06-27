import ast
import os
import platform
import shutil
import tarfile
import tempfile
from collections import namedtuple
from pathlib import Path
from typing import Dict, Any

import astor
import nbconvert
import yaml
from nbformat.notebooknode import NotebookNode

from .iotypes import CWLFilePathInput, CWLBooleanInput, CWLIntInput, CWLStringInput, CWLFilePathOutput
from .requirements_manager import RequirementsManager

with open(os.sep.join([os.path.abspath(os.path.dirname(__file__)), 'templates', 'template.dockerfile'])) as f:
    DOCKERFILE_TEMPLATE = f.read()
with open(os.sep.join([os.path.abspath(os.path.dirname(__file__)), 'templates', 'template.setup'])) as f:
    SETUP_TEMPLATE = f.read()


# TODO: does not support recursion if main function exists

class AnnotatedVariablesExtractor(ast.NodeTransformer):
    input_type_mapper = {
        CWLFilePathInput.__name__: (
            'File',
            'pathlib.Path',
        ),
        CWLBooleanInput.__name__: (
            'boolean',
            'lambda flag: flag.upper() == "TRUE"',
        ),
        CWLIntInput.__name__: (
            'int',
            'int',
        ),
        CWLStringInput.__name__: (
            'string',
            'str',
        ),
    }
    output_type_mapper = {
        CWLFilePathOutput.__name__
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extracted_nodes = []

    def visit_AnnAssign(self, node):
        try:
            if (isinstance(node.annotation, ast.Name) and node.annotation.id in self.input_type_mapper) or \
                    (isinstance(node.annotation, ast.Str) and node.annotation.s in self.input_type_mapper):
                mapper = self.input_type_mapper[node.annotation.id]
                self.extracted_nodes.append(
                    (node, mapper[0], mapper[1], True, True, False)
                )
                return None
            elif isinstance(node.annotation, ast.Subscript):
                if node.annotation.value.id == "Optional" \
                        and node.annotation.slice.value.id in self.input_type_mapper:
                    mapper = self.input_type_mapper[node.annotation.slice.value.id]
                    self.extracted_nodes.append(
                        (node, mapper[0] + '?', mapper[1], False, True, False)
                    )
                    return None
                elif node.annotation.value.id == "List" \
                        and node.annotation.slice.value.id in self.input_type_mapper:
                    mapper = self.input_type_mapper[node.annotation.slice.value.id]
                    self.extracted_nodes.append(
                        (node, mapper[0] + '[]', mapper[1], True, True, False)
                    )
                    return None
            elif (isinstance(node.annotation, ast.Name) and node.annotation.id in self.output_type_mapper) or \
                    (isinstance(node.annotation, ast.Str) and node.annotation.s in self.output_type_mapper):
                self.extracted_nodes.append(
                    (node, None, None, None, False, True)
                )
                # removing type annotation
                return ast.Assign(
                    col_offset=node.col_offset,
                    lineno=node.lineno,
                    targets=[node.target],
                    value=node.value
                )
        except AttributeError:
            pass
        return node

    def visit_Import(self, node: ast.Import):
        names = []
        for name in node.names:  # type: ast.alias
            if name.name == 'ipython2cwl' or name.name.startswith('ipython2cwl.'):
                continue
            names.append(name)
        if len(names) > 0:
            node.names = names
            return node
        else:
            return None

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module == 'ipython2cwl' or node.module.startswith('ipython2cwl.'):
            return None
        return node


class AnnotatedIPython2CWLToolConverter:
    """
    That class parses an annotated python script and generates a CWL Command Line Tool
    with the described inputs & outputs.
    """

    _code: str

    _VariableNameTypePair = namedtuple(
        'VariableNameTypePair',
        ['name', 'cwl_typeof', 'argparse_typeof', 'required', 'is_input', 'is_output', 'value']
    )

    """The annotated python code to convert."""

    def __init__(self, annotated_ipython_code: str):
        """Creates an AnnotatedIPython2CWLToolConverter. If the annotated_ipython_code contains magic commands use the
        from_jupyter_notebook_node method"""

        self._code = annotated_ipython_code
        extractor = AnnotatedVariablesExtractor()
        self._tree = ast.fix_missing_locations(extractor.visit(ast.parse(self._code)))
        self._variables = []
        for node, cwl_type, click_type, required, is_input, is_output in extractor.extracted_nodes:
            if is_input:
                self._variables.append(
                    self._VariableNameTypePair(node.target.id, cwl_type, click_type, required, is_input, is_output,
                                               None)
                )
            if is_output:
                self._variables.append(
                    self._VariableNameTypePair(node.target.id, cwl_type, click_type, required, is_input, is_output,
                                               node.value.s)
                )

    @classmethod
    def from_jupyter_notebook_node(cls, node: NotebookNode) -> 'AnnotatedIPython2CWLToolConverter':
        python_exporter = nbconvert.PythonExporter()
        code = python_exporter.from_notebook_node(node)[0]
        return cls(code)

    @classmethod
    def _wrap_script_to_method(cls, tree, variables) -> str:
        main_template_code = os.linesep.join([
            f"def main({','.join([v.name for v in variables if v.is_input])}):",
            "\tpass",
            "if __name__ == '__main__':",
            *['\t' + line for line in [
                "import argparse",
                'import pathlib',
                "parser = argparse.ArgumentParser()",
                *[f'parser.add_argument("--{variable.name}", '
                  f'type={variable.argparse_typeof}, '
                  f'required={variable.required})'
                  for variable in variables],
                "args = parser.parse_args()",
                f"main({','.join([f'{v.name}=args.{v.name}' for v in variables if v.is_input])})"
            ]],
        ])
        main_function = ast.parse(main_template_code)
        [node for node in main_function.body if isinstance(node, ast.FunctionDef) and node.name == 'main'][0] \
            .body = tree.body
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
            'outputs': {
                out.name: {
                    'type': 'File',
                    'outputBinding': {
                        'glob': out.value
                    }
                }
                for out in outputs
            },
        }
        return cwl_tool

    def compile(self, filename: Path = Path('notebookAsCWLTool.tar')) -> str:
        """
        That method generates a tar file which includes the following files:
        notebookTool - the python script
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
