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

from .iotypes import (
    CWLFilePathInput,
    CWLBooleanInput,
    CWLIntInput,
    CWLFloatInput,
    CWLStringInput,
    CWLFilePathOutput,
    CWLDirectoryPathOutput,
    CWLDumpableFile,
    CWLDumpableBinaryFile,
    CWLDumpable,
    CWLPNGPlot,
    CWLPNGFigure,
    CWLRequirement,
    CWLMetadata,
    CWLNamespaces,
)
from .requirements_manager import RequirementsManager

with open(
    os.sep.join(
        [os.path.abspath(os.path.dirname(__file__)), "templates", "template.dockerfile"]
    )
) as f:
    DOCKERFILE_TEMPLATE = f.read()
with open(
    os.sep.join(
        [os.path.abspath(os.path.dirname(__file__)), "templates", "template.setup"]
    )
) as f:
    SETUP_TEMPLATE = f.read()

_VariableNameTypePair = namedtuple(
    "VariableNameTypePair",
    [
        "name",
        "cwl_typeof",
        "argparse_typeof",
        "required",
        "is_input",
        "is_output",
        "value",
    ],
)


class AnnotatedVariablesExtractor(ast.NodeTransformer):
    """AnnotatedVariablesExtractor removes the typing annotations
    from relative to ipython2cwl and identifies all the variables
    relative to an ipython2cwl typing annotation."""

    input_type_mapper: Dict[Tuple[str, ...], Tuple[str, str]] = {
        (CWLFilePathInput.__name__,): (
            "File",
            "pathlib.Path",
        ),
        (CWLBooleanInput.__name__,): (
            "boolean",
            'lambda flag: flag.upper() == "TRUE"',
        ),
        (CWLIntInput.__name__,): (
            "int",
            "int",
        ),
        (CWLFloatInput.__name__,): (
            "float",
            "float",
        ),
        (CWLStringInput.__name__,): (
            "string",
            "str",
        ),
    }
    input_type_mapper = {
        **input_type_mapper,
        **{
            ("List", *(t for t in types_names)): (types[0] + "[]", types[1])
            for types_names, types in input_type_mapper.items()
        },
        **{
            ("Optional", *(t for t in types_names)): (types[0] + "?", types[1])
            for types_names, types in input_type_mapper.items()
        },
    }

    output_type_mapper = {
        (CWLFilePathOutput.__name__,),
        (CWLDirectoryPathOutput.__name__,),
    }

    dumpable_mapper = {
        (CWLDumpableFile.__name__,): (
            (
                None,
                "with open('{var_name}', 'w') as f:\n\tf.write({var_name})",
            ),
            lambda node: node.target.id,
        ),
        (CWLDumpableBinaryFile.__name__,): (
            (None, "with open('{var_name}', 'wb') as f:\n\tf.write({var_name})"),
            lambda node: node.target.id,
        ),
        (CWLDumpable.__name__, CWLDumpable.dump.__name__): None,
        (CWLPNGPlot.__name__,): (
            (None, '{var_name}[-1].figure.savefig("{var_name}.png")'),
            lambda node: str(node.target.id) + ".png",
        ),
        (CWLPNGFigure.__name__,): (
            (
                "import matplotlib.pyplot as plt\nplt.figure()",
                '{var_name}[-1].figure.savefig("{var_name}.png")',
            ),
            lambda node: str(node.target.id) + ".png",
        ),
    }

    def __init__(self, *args, **kwargs):
        """Create an AnnotatedVariablesExtractor"""
        super().__init__(*args, **kwargs)
        self.extracted_variables: List = []
        self.to_dump: List = []
        self.cwl_requirements: Dict = {}
        self.cwl_metadata: Dict = {}
        self.cwl_namespaces: Dict = {}

    def __get_annotation__(self, type_annotation):
        """Parses the annotation and returns it in a canonical format.
        If the annotation was a string 'CWLStringInput' the function
        will return you the object."""
        annotation = None
        if isinstance(type_annotation, ast.Name):
            annotation = (type_annotation.id,)
        elif isinstance(type_annotation, ast.Str):
            # Parse the string annotation (Python < 3.8)
            try:
                ann_expr = ast.parse(type_annotation.s.strip()).body[0]
                if hasattr(ann_expr, "value"):
                    annotation = self.__get_annotation__(ann_expr.value)
                else:
                    annotation = (type_annotation.s,)
            except Exception:
                annotation = (type_annotation.s,)
        elif isinstance(type_annotation, ast.Constant) and isinstance(
            type_annotation.value, str
        ):
            # Parse the string annotation (Python >= 3.8)
            try:
                ann_expr = ast.parse(type_annotation.value.strip()).body[0]
                if hasattr(ann_expr, "value"):
                    annotation = self.__get_annotation__(ann_expr.value)
                else:
                    annotation = (type_annotation.value,)
            except Exception:
                annotation = (type_annotation.value,)
        elif isinstance(type_annotation, ast.Subscript):
            # Handle both old and new AST formats
            slice_value = type_annotation.slice

            # Handle Optional[Type] and List[Type] patterns
            if isinstance(slice_value, ast.Name):
                inner_annotation = self.__get_annotation__(slice_value)
            elif isinstance(slice_value, ast.Str):
                inner_annotation = self.__get_annotation__(slice_value)
            elif isinstance(slice_value, ast.Constant) and isinstance(
                slice_value.value, str
            ):
                # For string constants like "CWLBooleanInput"
                inner_annotation = (slice_value.value,)
            elif hasattr(slice_value, "value"):  # Old format (Python < 3.9)
                inner_annotation = self.__get_annotation__(slice_value.value)
            else:
                inner_annotation = ()

            annotation = (type_annotation.value.id, *inner_annotation)
        elif isinstance(type_annotation, ast.Call):
            annotation = (type_annotation.func.value.id, type_annotation.func.attr)
        return annotation

    @classmethod
    def conv_AnnAssign_to_Assign(cls, node):
        return ast.Assign(
            col_offset=node.col_offset,
            lineno=node.lineno,
            targets=[node.target],
            value=node.value,
        )

    def _visit_input_ann_assign(self, node, annotation):
        mapper = self.input_type_mapper[annotation]

        # Extract the actual value from the assignment
        value = None
        if node.value is not None:
            if isinstance(node.value, ast.Constant):
                value = node.value.value
            elif hasattr(node.value, "s"):  # Python < 3.8 compatibility
                value = node.value.s

        self.extracted_variables.append(
            _VariableNameTypePair(
                node.target.id,
                mapper[0],
                mapper[1],
                not mapper[0].endswith("?"),
                True,
                False,
                value,
            )
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
            post_code_body = ast.parse(
                dumper[0][1].format(var_name=node.target.id)
            ).body
        self.extracted_variables.append(
            _VariableNameTypePair(
                node.target.id, "File", None, None, False, True, dumper[1](node)
            )
        )
        return [*pre_code_body, self.conv_AnnAssign_to_Assign(node), *post_code_body]

    def _visit_user_defined_dumper(self, node):
        load_ctx = ast.Load()
        func_name = deepcopy(node.annotation.args[0].value)
        func_name.ctx = load_ctx
        ast.fix_missing_locations(func_name)

        new_dump_node = ast.Expr(
            col_offset=0,
            lineno=0,
            value=ast.Call(
                args=node.annotation.args[1:],
                keywords=node.annotation.keywords,
                col_offset=0,
                func=ast.Attribute(
                    attr=node.annotation.args[0].attr,
                    value=func_name,
                    col_offset=0,
                    ctx=load_ctx,
                    lineno=0,
                ),
            ),
        )
        ast.fix_missing_locations(new_dump_node)
        self.to_dump.append([new_dump_node])
        self.extracted_variables.append(
            _VariableNameTypePair(
                node.target.id, "File", None, None, False, True, node.annotation.args[1].s
            )
        )
        # removing type annotation
        return self.conv_AnnAssign_to_Assign(node)

    def _resolve_variable_value(self, var_name):
        """Resolve the value of a variable from extracted variables."""
        for var in self.extracted_variables:
            if var.name == var_name and var.is_input:
                return var.value
        return None

    def _resolve_output_path(self, node):
        """Resolve output path expressions for CWL glob patterns."""
        import astor

        # Handle direct variable reference
        if isinstance(node.value, ast.Name):
            var_value = self._resolve_variable_value(node.value.id)
            if var_value is not None:
                return var_value
            # Fallback to variable name if not found
            return node.value.id

        # Simple string constant
        if hasattr(node.value, "s"):
            return node.value.s
        elif hasattr(node.value, "value") and isinstance(node.value.value, str):
            return node.value.value

        # Handle os.path.join() expressions
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Attribute)
            and node.value.func.value.attr == "path"
            and node.value.func.attr == "join"
        ):

            # Extract arguments from os.path.join(arg1, arg2, ...)
            args = []
            for arg in node.value.args:
                if isinstance(arg, ast.Name):
                    # Try to resolve variable value first
                    var_value = self._resolve_variable_value(arg.id)
                    if var_value is not None:
                        args.append(var_value)
                    else:
                        # Fallback to variable name
                        args.append(arg.id)
                elif hasattr(arg, "s"):
                    args.append(arg.s)
                elif hasattr(arg, "value") and isinstance(arg.value, str):
                    args.append(arg.value)
                else:
                    # Fallback to source code
                    try:
                        args.append(astor.to_source(arg).strip().strip("'\""))
                    except:
                        args.append(str(arg))

            # Join with forward slashes for CWL
            return "/".join(args)

        # Fallback: convert to source and try to clean it up
        try:
            source = astor.to_source(node.value).strip()
            # Simple cleanup for common patterns
            if source.startswith("os.path.join(output_dir, '") and source.endswith(
                "')"
            ):
                filename = source.split("', '")[1].rstrip("')")
                return f"outputs/{filename}"
            return source
        except:
            return str(node.value)

    def _visit_output_type(self, node, annotation):
        # Resolve the output path for CWL compatibility
        value_str = self._resolve_output_path(node)

        # Determine CWL type based on annotation
        if annotation == (CWLDirectoryPathOutput.__name__,):
            cwl_type = "Directory"
        else:  # CWLFilePathOutput
            cwl_type = "File"

        self.extracted_variables.append(
            _VariableNameTypePair(
                node.target.id, cwl_type, None, None, False, True, value_str
            )
        )
        # removing type annotation
        return ast.Assign(
            col_offset=node.col_offset,
            lineno=node.lineno,
            targets=[node.target],
            value=node.value,
        )

    def _visit_cwl_requirement(self, node):
        """Process CWLRequirement annotations to extract CWL requirements."""
        try:
            # Extract the dictionary from the CWLRequirement call
            dict_node = None
            if isinstance(node.value, ast.Call) and len(node.value.args) > 0:
                dict_node = node.value.args[0]  # First argument is the dict
            elif isinstance(node.value, ast.Dict):
                dict_node = node.value

            if isinstance(dict_node, ast.Dict):
                # Try to extract the dictionary content
                for key, value in zip(dict_node.keys, dict_node.values):
                    if isinstance(key, (ast.Str, ast.Constant)):
                        key_str = key.s if hasattr(key, "s") else key.value
                        if isinstance(value, ast.Dict):
                            # Parse nested dictionary
                            nested_dict = {}
                            for nested_key, nested_value in zip(
                                value.keys, value.values
                            ):
                                if isinstance(nested_key, (ast.Str, ast.Constant)):
                                    nested_key_str = (
                                        nested_key.s
                                        if hasattr(nested_key, "s")
                                        else nested_key.value
                                    )
                                    if isinstance(
                                        nested_value, (ast.Str, ast.Constant)
                                    ):
                                        nested_value_val = (
                                            nested_value.s
                                            if hasattr(nested_value, "s")
                                            else nested_value.value
                                        )
                                    elif isinstance(
                                        nested_value, (ast.NameConstant, ast.Constant)
                                    ) and isinstance(nested_value.value, bool):
                                        nested_value_val = nested_value.value
                                    elif hasattr(nested_value, "n"):  # numbers
                                        nested_value_val = nested_value.n
                                    elif hasattr(nested_value, "value") and isinstance(
                                        nested_value.value, (int, float)
                                    ):
                                        nested_value_val = nested_value.value
                                    else:
                                        continue
                                    nested_dict[nested_key_str] = nested_value_val
                            self.cwl_requirements[key_str] = nested_dict
        except Exception:
            # If we can't parse it, ignore silently
            pass

        # Remove the annotation and return the assignment
        return ast.Assign(
            col_offset=node.col_offset,
            lineno=node.lineno,
            targets=[node.target],
            value=node.value,
        )

    def _visit_cwl_metadata(self, node):
        """Process CWLMetadata annotations to extract CWL schema.org metadata."""
        try:
            # Extract the dictionary from the CWLMetadata call
            dict_node = None
            if isinstance(node.value, ast.Call) and len(node.value.args) > 0:
                dict_node = node.value.args[0]  # First argument is the dict
            elif isinstance(node.value, ast.Dict):
                dict_node = node.value

            if isinstance(dict_node, ast.Dict):
                # Try to extract the dictionary content
                for key, value in zip(dict_node.keys, dict_node.values):
                    if isinstance(key, (ast.Str, ast.Constant)):
                        key_str = key.s if hasattr(key, "s") else key.value

                        # Handle different value types
                        if isinstance(value, ast.Dict):
                            # Parse nested dictionary (for complex structures like author)
                            nested_dict = {}
                            for nested_key, nested_value in zip(
                                value.keys, value.values
                            ):
                                if isinstance(nested_key, (ast.Str, ast.Constant)):
                                    nested_key_str = (
                                        nested_key.s
                                        if hasattr(nested_key, "s")
                                        else nested_key.value
                                    )
                                    nested_value_val = self._parse_ast_value(
                                        nested_value
                                    )
                                    if nested_value_val is not None:
                                        nested_dict[nested_key_str] = nested_value_val
                            self.cwl_metadata[key_str] = nested_dict
                        elif isinstance(value, ast.List):
                            # Parse lists (for arrays like keywords or multiple authors)
                            list_values = []
                            for list_item in value.elts:
                                if isinstance(list_item, ast.Dict):
                                    # Handle list of dictionaries (like multiple authors)
                                    dict_item = {}
                                    for dict_key, dict_value in zip(
                                        list_item.keys, list_item.values
                                    ):
                                        if isinstance(
                                            dict_key, (ast.Str, ast.Constant)
                                        ):
                                            dict_key_str = (
                                                dict_key.s
                                                if hasattr(dict_key, "s")
                                                else dict_key.value
                                            )
                                            dict_value_val = self._parse_ast_value(
                                                dict_value
                                            )
                                            if dict_value_val is not None:
                                                dict_item[dict_key_str] = dict_value_val
                                    list_values.append(dict_item)
                                else:
                                    # Handle list of simple values
                                    list_value = self._parse_ast_value(list_item)
                                    if list_value is not None:
                                        list_values.append(list_value)
                            self.cwl_metadata[key_str] = list_values
                        else:
                            # Handle simple values
                            simple_value = self._parse_ast_value(value)
                            if simple_value is not None:
                                self.cwl_metadata[key_str] = simple_value
        except Exception:
            # If we can't parse it, ignore silently
            pass

        # Remove the annotation and return the assignment
        return ast.Assign(
            col_offset=node.col_offset,
            lineno=node.lineno,
            targets=[node.target],
            value=node.value,
        )

    def _visit_cwl_namespaces(self, node):
        """Process CWLNamespaces annotations to extract CWL namespaces."""
        try:
            # Extract the dictionary from the CWLNamespaces call
            dict_node = None
            if isinstance(node.value, ast.Call) and len(node.value.args) > 0:
                dict_node = node.value.args[0]  # First argument is the dict
            elif isinstance(node.value, ast.Dict):
                dict_node = node.value

            if isinstance(dict_node, ast.Dict):
                # Try to extract the dictionary content
                for key, value in zip(dict_node.keys, dict_node.values):
                    if isinstance(key, (ast.Str, ast.Constant)):
                        key_str = key.s if hasattr(key, "s") else key.value
                        # Handle simple values (namespaces are typically simple string mappings)
                        simple_value = self._parse_ast_value(value)
                        if simple_value is not None:
                            self.cwl_namespaces[key_str] = simple_value
        except Exception:
            # If we can't parse it, ignore silently
            pass

        # Remove the annotation and return the assignment
        return ast.Assign(
            col_offset=node.col_offset,
            lineno=node.lineno,
            targets=[node.target],
            value=node.value,
        )

    def _parse_ast_value(self, value_node):
        """Helper method to parse various AST value types."""
        if isinstance(value_node, (ast.Str, ast.Constant)):
            return value_node.s if hasattr(value_node, "s") else value_node.value
        elif isinstance(value_node, (ast.NameConstant, ast.Constant)) and isinstance(
            value_node.value, bool
        ):
            return value_node.value
        elif hasattr(value_node, "n"):  # numbers in older Python versions
            return value_node.n
        elif hasattr(value_node, "value") and isinstance(
            value_node.value, (int, float)
        ):
            return value_node.value
        return None

    def visit_Assign(self, node):
        """Handle simple assignments (without type annotations)"""
        try:
            # Check if this is a call to one of our CWL classes
            if isinstance(node.value, ast.Call) and isinstance(
                node.value.func, ast.Name
            ):
                func_name = node.value.func.id
                if func_name == CWLRequirement.__name__:
                    return self._visit_cwl_requirement(node)
                elif func_name == CWLMetadata.__name__:
                    return self._visit_cwl_metadata(node)
                elif func_name == CWLNamespaces.__name__:
                    return self._visit_cwl_namespaces(node)
                elif func_name in [
                    cls.__name__ for cls in self.input_type_mapper.keys()
                ]:
                    # Handle CWL input types
                    annotation = (func_name,)
                    if annotation in self.input_type_mapper:
                        return self._visit_input_ann_assign(node, annotation)
                elif func_name in [
                    cls.__name__ for cls in self.output_type_mapper.keys()
                ]:
                    # Handle CWL output types
                    return self._visit_output_type(node)
        except Exception:
            pass
        return node

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
                return self._visit_output_type(node, annotation)
            elif annotation == (CWLRequirement.__name__,):
                return self._visit_cwl_requirement(node)
            elif annotation == (CWLMetadata.__name__,):
                return self._visit_cwl_metadata(node)
            elif annotation == (CWLNamespaces.__name__,):
                return self._visit_cwl_namespaces(node)
        except Exception:
            pass
        return node

    def visit_Import(self, node: ast.Import) -> Any:
        """Remove ipython2cwl imports"""
        names = []
        for name in node.names:  # type: ast.alias
            if name.name == "ipython2cwl" or name.name.startswith("ipython2cwl."):
                continue
            names.append(name)
        if len(names) > 0:
            node.names = names
            return node
        else:
            return None

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        """Remove ipython2cwl imports"""
        if node.module == "ipython2cwl" or (
            node.module is not None and node.module.startswith("ipython2cwl.")
        ):
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
        self._cwl_requirements = extractor.cwl_requirements
        self._cwl_metadata = extractor.cwl_metadata
        self._cwl_namespaces = extractor.cwl_namespaces

    @classmethod
    def from_jupyter_notebook_node(
        cls, node: NotebookNode
    ) -> "AnnotatedIPython2CWLToolConverter":
        python_exporter = nbconvert.PythonExporter()
        code = python_exporter.from_notebook_node(node)[0]
        return cls(code)

    @classmethod
    def _wrap_script_to_method(cls, tree, variables) -> str:
        add_args = cls.__get_add_arguments__([v for v in variables if v.is_input])
        main_template_code = os.linesep.join(
            [
                f"def main({','.join([v.name for v in variables if v.is_input])}):",
                "\tpass",
                "if __name__ == '__main__':",
                *[
                    "\t" + line
                    for line in [
                        "import argparse",
                        "import pathlib",
                        "parser = argparse.ArgumentParser()",
                        *add_args,
                        "args = parser.parse_args()",
                        f"main({','.join([f'{v.name}=args.{v.name} ' for v in variables if v.is_input])})",
                    ]
                ],
            ]
        )
        main_function = ast.parse(main_template_code)
        [
            node
            for node in main_function.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        ][0].body = tree.body
        return astor.to_source(main_function)

    @classmethod
    def __get_add_arguments__(cls, variables):
        args = []
        for variable in variables:
            is_array = variable.cwl_typeof.endswith("[]")
            is_optional = variable.cwl_typeof.endswith("?")
            arg: str = f'parser.add_argument("--{variable.name}", '
            arg += f"type={variable.argparse_typeof}, "
            arg += f"required={variable.required}, "
            if is_array:
                arg += f'nargs="+", '
            if is_optional:
                arg += f"default=None, "
            arg = arg.strip()
            arg += ")"
            args.append(arg)
        return args

    def cwl_command_line_tool(self, docker_image_id: str = "jn2cwl:latest") -> Dict:
        """
        Creates the description of the CWL Command Line Tool.
        :return: The cwl description of the corresponding tool
        """
        inputs = [v for v in self._variables if v.is_input]
        outputs = [v for v in self._variables if v.is_output]

        # Build CWL tool dictionary with proper ordering
        cwl_tool = {}

        # Add namespaces first (if any)
        if self._cwl_namespaces:
            cwl_tool["$namespaces"] = self._cwl_namespaces

        # Add core CWL fields
        cwl_tool.update(
            {
                "cwlVersion": "v1.1",
                "class": "CommandLineTool",
                "baseCommand": "notebookTool",
                "hints": {"DockerRequirement": {"dockerImageId": docker_image_id}},
                "arguments": ["--"],
                "inputs": {
                    input_var.name: {
                        "type": input_var.cwl_typeof,
                        "inputBinding": {"prefix": f"--{input_var.name}"},
                    }
                    for input_var in inputs
                },
                "outputs": {
                    out.name: {"type": out.cwl_typeof, "outputBinding": {"glob": out.value}}
                    for out in outputs
                },
            }
        )

        # Add extracted CWL requirements
        if self._cwl_requirements:
            cwl_tool["requirements"] = self._cwl_requirements

        # Add extracted CWL metadata
        if self._cwl_metadata:
            cwl_tool.update(self._cwl_metadata)

        return cwl_tool

    def compile(self, filename: Path = Path("notebookAsCWLTool.tar")) -> str:
        """
        That method generates a tar file which includes the following files:
        notebookTool - the python script
        tool.cwl - the cwl description file
        Dockerfile - the dockerfile to create the docker image
        :param: filename
        :return: The absolute path of the tar file
        """
        workdir = tempfile.mkdtemp()
        script_path = os.path.join(workdir, "notebookTool")
        cwl_path: str = os.path.join(workdir, "tool.cwl")
        dockerfile_path = os.path.join(workdir, "Dockerfile")
        setup_path = os.path.join(workdir, "setup.py")
        requirements_path = os.path.join(workdir, "requirements.txt")
        with open(script_path, "wb") as script_fd:
            script_fd.write(
                self._wrap_script_to_method(self._tree, self._variables).encode()
            )
        with open(cwl_path, "w") as cwl_fd:
            yaml.safe_dump(self.cwl_command_line_tool(), cwl_fd, encoding="utf-8")
        dockerfile = DOCKERFILE_TEMPLATE.format(
            python_version=f'python:{".".join(platform.python_version_tuple())}'
        )
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile)
        with open(setup_path, "w") as f:
            f.write(SETUP_TEMPLATE)

        with open(requirements_path, "w") as f:
            f.write(os.linesep.join(RequirementsManager.get_all()))

        with tarfile.open(str(filename.absolute()), "w") as tar_fd:

            def add_tar(file_to_add):
                tar_fd.add(file_to_add, arcname=os.path.basename(file_to_add))

            add_tar(script_path)
            add_tar(cwl_path)
            add_tar(dockerfile_path)
            add_tar(setup_path)
            add_tar(requirements_path)

        shutil.rmtree(workdir)
        return str(filename.absolute())
