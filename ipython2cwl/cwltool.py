import os
from pathlib import Path
from typing import List, Dict

import ast
import astor
from collections import namedtuple

from .iotypes import CWLFileInput
from . import iotypes


class CWLToolBuilder(object):
    """CWLToolBuilder is a singleton class which builds a CWL CommandLineTool
    by providing decorators as interface.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if CWLToolBuilder._instance is None:
            CWLToolBuilder._instance = object.__new__(cls)
        CWLToolBuilder._instance.cwl_inputs = []
        return CWLToolBuilder._instance

    def register_input(self, func):
        func()
        return func


# TODO: does not support recursion if main function exists

class AnnotatedIPython2CWLToolConverter:
    """
    That class parses an annotated python script and generates a CWL Command Line Tool
    with the described inputs & outputs.
    """

    _code: str

    _VariableNameAnnotationPair = namedtuple('VariableNameTypePair', ['name', 'typeof'])

    """The annotated python code to convert."""

    def __init__(self, annotated_ipython_code: str):
        self._code = annotated_ipython_code

    @classmethod
    def _get_input_from_code(cls, code) -> List[_VariableNameAnnotationPair]:
        variables = []
        for node in ast.walk(ast.parse(code)):
            try:
                if node.annotation.id == 'CWLFileInput':
                    variables.append(cls._VariableNameAnnotationPair(node.target.id, CWLFileInput))
            except AttributeError:
                pass
        return variables

    @classmethod
    def _wrap_script_to_method(cls, code, variables) -> str:

        main_function = ast.parse(os.linesep.join([
            'import click',
            '@click.command()',
            *[f'@click.option("--{variable.name}", type="{variable.typeof.to_click_method()}")'
              for variable in variables],
            f"def main({','.join([variable.name for variable in variables])}):",
            "\tpass"
        ]))
        tree = ast.parse(code)
        main_function.body[-1].body = tree.body
        return astor.to_source(main_function)

    def cwl_command_line_tool(self) -> Dict:
        """
        Creates the descrption of the CWL Command Line Tool.
        :return: The cwl description of the corresponding tool
        """
        variables = self._get_input_from_code(self._code)
        inputs = [v for v in variables if v.typeof.__name__ in iotypes.inputs]
        outputs = [v for v in variables if v.typeof.__name__ in iotypes.outputs]

        cwl_tool = {
            'cwlVersion': "v1.1",
            'class': 'CommandLineTool',
            'baseCommand': 'python',
            'arguments': [{'position': 0, 'valueFrom': 'tool.py'}],
            'inputs': [{
                input_var.name: {
                    'type': input_var.typeof.to_cwl(),
                    'inputBinding': {
                        'prefix': f'--{input_var.name}'
                    }
                }
            } for input_var in inputs],
            'outputs': list(outputs),
        }
        return cwl_tool

    def compile(self, filename: Path):
        """
        That method generates a tar file which includes the following files:
        main.py - the python script
        tool.cwl - the cwl description file
        :return:
        """
        raise NotImplementedError('')