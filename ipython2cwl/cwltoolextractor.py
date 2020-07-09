import ast
import os
import platform
import shutil
import tarfile
import tempfile
from collections import namedtuple
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any, List, Tuple

import astor  # type: ignore
import nbconvert  # type: ignore
import yaml
from nbformat.notebooknode import NotebookNode  # type: ignore

from .iotypes import CWLFilePathInput, CWLBooleanInput, CWLIntInput, CWLStringInput, CWLFilePathOutput, \
    CWLDumpableFile, CWLDumpableBinaryFile, CWLDumpable, CWLPNGPlot, CWLPNGFigure
from .requirements_manager import RequirementsManager

with open(os.sep.join([os.path.abspath(os.path.dirname(__file__)), 'templates', 'template.dockerfile'])) as f:
    DOCKERFILE_TEMPLATE = f.read()
with open(os.sep.join([os.path.abspath(os.path.dirname(__file__)), 'templates', 'template.setup'])) as f:
    SETUP_TEMPLATE = f.read()

_VariableNameTypePair = namedtuple(
    'VariableNameTypePair',
    ['name', 'cwl_typeof', 'argparse_typeof', 'required', 'is_input', 'is_output', 'value']
)


class AnnotatedVariablesExtractor(ast.NodeTransformer):
    """AnnotatedVariablesExtractor removes the typing annotations
        from relative to ipython2cwl and identifies all the variables
        relative to an ipython2cwl typing annotation."""
    input_type_mapper: Dict[Tuple[str, ...], Tuple[str, str]] = {
        (CWLFilePathInput.__name__,): (
            'File',
            'pathlib.Path',
        ),
        (CWLBooleanInput.__name__,): (
            'boolean',
            'lambda flag: flag.upper() == "TRUE"',
        ),
        (CWLIntInput.__name__,): (
            'int',
            'int',
        ),
        (CWLStringInput.__name__,): (
            'string',
            'str',
        ),
    }
    input_type_mapper = {**input_type_mapper, **{
        ('List', *(t for t in types_names)): (types[0] + "[]", types[1])
        for types_names, types in input_type_mapper.items()
    }, **{
        ('Optional', *(t for t in types_names)): (types[0] + "?", types[1])
        for types_names, types in input_type_mapper.items()
    }}

    output_type_mapper = {
        (CWLFilePathOutput.__name__,)
    }

    dumpable_mapper = {
        (CWLDumpableFile.__name__,): (
            (None, "with open('{var_name}', 'w') as f:\n\tf.write({var_name})",),
            lambda node: node.target.id
        ),
        (CWLDumpableBinaryFile.__name__,): (
            (None, "with open('{var_name}', 'wb') as f:\n\tf.write({var_name})"),
            lambda node: node.target.id
        ),
        (CWLDumpable.__name__, CWLDumpable.dump.__name__): None,
        (CWLPNGPlot.__name__,): (
            (None, '{var_name}[-1].figure.savefig("{var_name}.png")'),
            lambda node: str(node.target.id) + '.png'),
        (CWLPNGFigure.__name__,): (
            ('import matplotlib.pyplot as plt\nplt.figure()', '{var_name}[-1].figure.savefig("{var_name}.png")'),
            lambda node: str(node.target.id) + '.png'),
    }

    def __init__(self, *args, **kwargs):
        """Create an AnnotatedVariablesExtractor"""
        super().__init__(*args, **kwargs)
        self.extracted_variables: List = []
        self.to_dump: List = []

    def __get_annotation__(self, type_annotation):
        """Parses the annotation and returns it in a canonical format.
        If the annotation was a string 'CWLStringInput' the function
        will return you the object."""
        annotation = None
        if isinstance(type_annotation, ast.Name):
            annotation = (type_annotation.id,)
        elif isinstance(type_annotation, ast.Str):
            annotation = (type_annotation.s,)
            ann_expr = ast.parse(type_annotation.s.strip()).body[0]
            if hasattr(ann_expr, 'value') and isinstance(ann_expr.value, ast.Subscript):
                annotation = self.__get_annotation__(ann_expr.value)
        elif isinstance(type_annotation, ast.Subscript):
            annotation = (type_annotation.value.id, *self.__get_annotation__(type_annotation.slice.value))
        elif isinstance(type_annotation, ast.Call):
            annotation = (type_annotation.func.value.id, type_annotation.func.attr)
        return annotation

    @classmethod
    def conv_AnnAssign_to_Assign(cls, node):
        return ast.Assign(
            col_offset=node.col_offset,
            lineno=node.lineno,
            targets=[node.target],
            value=node.value
        )

    def _visit_input_ann_assign(self, node, annotation):
        mapper = self.input_type_mapper[annotation]
        self.extracted_variables.append(_VariableNameTypePair(
            node.target.id, mapper[0], mapper[1], not mapper[0].endswith('?'), True, False, None)
        )
        return None

    def _visit_default_dumper(self, node, dumper):
        if dumper[0][0] is None:
            pre_code_body = []
        else:
            pre_code_body = ast.parse(dumper[0][0].format(var_name=node.target.id)).body
        if dumper[0][1] is None:
            post_code_body = []
        else:
            post_code_body = ast.parse(dumper[0][1].format(var_name=node.target.id)).body
        self.extracted_variables.append(_VariableNameTypePair(
            node.target.id, None, None, None, False, True, dumper[1](node))
        )
        return [*pre_code_body, self.conv_AnnAssign_to_Assign(node), *post_code_body]

    def _visit_user_defined_dumper(self, node):
        load_ctx = ast.Load()
        func_name = deepcopy(node.annotation.args[0].value)
        func_name.ctx = load_ctx
        ast.fix_missing_locations(func_name)

        new_dump_node = ast.Expr(
            col_offset=0, lineno=0,
            value=ast.Call(
                args=node.annotation.args[1:], keywords=node.annotation.keywords, col_offset=0,
                func=ast.Attribute(
                    attr=node.annotation.args[0].attr,
                    value=func_name,
                    col_offset=0, ctx=load_ctx, lineno=0,
                ),
            )
        )
        ast.fix_missing_locations(new_dump_node)
        self.to_dump.append([new_dump_node])
        self.extracted_variables.append(_VariableNameTypePair(
            node.target.id, None, None, None, False, True, node.annotation.args[1].s)
        )
        # removing type annotation
        return self.conv_AnnAssign_to_Assign(node)

    def _visit_output_type(self, node):
        self.extracted_variables.append(_VariableNameTypePair(
            node.target.id, None, None, None, False, True, node.value.s)
        )
        # removing type annotation
        return ast.Assign(
            col_offset=node.col_offset,
            lineno=node.lineno,
            targets=[node.target],
            value=node.value
        )

    def visit_AnnAssign(self, node):
        try:
            annotation = self.__get_annotation__(node.annotation)
            if annotation in self.input_type_mapper:
                return self._visit_input_ann_assign(node, annotation)
            elif annotation in self.dumpable_mapper:
                dumper = self.dumpable_mapper[annotation]
                if dumper is not None:
                    return self._visit_default_dumper(node, dumper)
                else:
                    return self._visit_user_defined_dumper(node)
            elif annotation in self.output_type_mapper:
                return self._visit_output_type(node)
        except Exception:
            pass
        return node

    def visit_Import(self, node: ast.Import) -> Any:
        """Remove ipython2cwl imports """
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
        """Remove ipython2cwl imports """
        if node.module == 'ipython2cwl' or (node.module is not None and node.module.startswith('ipython2cwl.')):
            return None
        return node


class AnnotatedIPython2CWLToolConverter:
    """
    That class parses an annotated python script and generates a CWL Command Line Tool
    with the described inputs & outputs.
    """

    _code: str  # The annotated python code to convert.

    def __init__(self, annotated_ipython_code: str):
        """Creates an AnnotatedIPython2CWLToolConverter. If the annotated_ipython_code contains magic commands use the
        from_jupyter_notebook_node method"""

        self._code = annotated_ipython_code
        extractor = AnnotatedVariablesExtractor()
        self._tree = extractor.visit(ast.parse(self._code))
        for d in extractor.to_dump:
            self._tree.body.extend(d)
        self._tree = ast.fix_missing_locations(self._tree)
        self._variables = []
        for variable in extractor.extracted_variables:  # type: _VariableNameTypePair
            if variable.is_input:
                self._variables.append(variable)
            if variable.is_output:
                self._variables.append(variable)

    @classmethod
    def from_jupyter_notebook_node(cls, node: NotebookNode) -> 'AnnotatedIPython2CWLToolConverter':
        python_exporter = nbconvert.PythonExporter()
        code = python_exporter.from_notebook_node(node)[0]
        return cls(code)

    @classmethod
    def _wrap_script_to_method(cls, tree, variables) -> str:
        add_args = cls.__get_add_arguments__([v for v in variables if v.is_input])
        main_template_code = os.linesep.join([
            f"def main({','.join([v.name for v in variables if v.is_input])}):",
            "\tpass",
            "if __name__ == '__main__':",
            *['\t' + line for line in [
                "import argparse",
                'import pathlib',
                "parser = argparse.ArgumentParser()",
                *add_args,
                "args = parser.parse_args()",
                f"main({','.join([f'{v.name}=args.{v.name} ' for v in variables if v.is_input])})"
            ]],
        ])
        main_function = ast.parse(main_template_code)
        [node for node in main_function.body if isinstance(node, ast.FunctionDef) and node.name == 'main'][0] \
            .body = tree.body
        return astor.to_source(main_function)

    @classmethod
    def __get_add_arguments__(cls, variables):
        args = []
        for variable in variables:
            is_array = variable.cwl_typeof.endswith('[]')
            is_optional = variable.cwl_typeof.endswith('?')
            arg: str = f'parser.add_argument("--{variable.name}", '
            arg += f'type={variable.argparse_typeof}, '
            arg += f'required={variable.required}, '
            if is_array:
                arg += f'nargs="+", '
            if is_optional:
                arg += f'default=None, '
            arg = arg.strip()
            arg += ')'
            args.append(arg)
        return args

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
            'arguments': ['--'],
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
        cwl_path: str = os.path.join(workdir, 'tool.cwl')
        dockerfile_path = os.path.join(workdir, 'Dockerfile')
        setup_path = os.path.join(workdir, 'setup.py')
        requirements_path = os.path.join(workdir, 'requirements.txt')
        with open(script_path, 'wb') as script_fd:
            script_fd.write(self._wrap_script_to_method(self._tree, self._variables).encode())
        with open(cwl_path, 'w') as cwl_fd:
            yaml.safe_dump(
                self.cwl_command_line_tool(),
                cwl_fd,
                encoding='utf-8'
            )
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
