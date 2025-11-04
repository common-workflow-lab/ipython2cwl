import os
import tarfile
import tempfile
from pathlib import Path
from unittest import TestCase

import nbformat

from ipython2cwl.cwltoolextractor import AnnotatedIPython2CWLToolConverter
from ipython2cwl.iotypes import CWLStringInput, CWLFilePathOutput


class TestCWLTool(TestCase):
    maxDiff = None

    def test_AnnotatedIPython2CWLToolConverter_cwl_command_line_tool(self):
        annotated_python_script = os.linesep.join(
            [
                "import csv",
                "input_filename: CWLFilePathInput = 'data.csv'",
                "flag: CWLBooleanInput = true",
                "num_int: CWLIntInput = 1",
                "num_float: CWLFloatInput = 1.0",
                "msg: CWLStringInput = 'hello world'",
                "with open(input_filename) as f:",
                "\tcsv_reader = csv.reader(f)",
                "\tdata = [line for line in reader]",
                "print(msg)",
                "print(num)",
                "print(flag)",
            ]
        )

        cwl_tool = AnnotatedIPython2CWLToolConverter(
            annotated_python_script
        ).cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}},
                'inputs': {
                    'input_filename': {
                        'type': 'File',
                        'inputBinding': {'prefix': '--input_filename'},
                    },
                    'flag': {'type': 'boolean', 'inputBinding': {'prefix': '--flag'}},
                    'num_int': {'type': 'int', 'inputBinding': {'prefix': '--num_int'}},
                    'num_float': {
                        'type': 'float',
                        'inputBinding': {'prefix': '--num_float'},
                    },
                    'msg': {'type': 'string', 'inputBinding': {'prefix': '--msg'}},
                },
                'outputs': {},
                'arguments': ['--'],
            },
            cwl_tool,
        )

    def test_AnnotatedIPython2CWLToolConverter_compile(self):
        annotated_python_script = os.linesep.join(
            [
                "import csv",
                "input_filename: CWLFilePathInput = 'data.csv'",
                "with open(input_filename) as f:",
                "\tcsv_reader = csv.reader(f)",
                "\tdata = [line for line in csv_reader]",
                "print(data)",
            ]
        )
        compiled_tar_file = os.path.join(tempfile.mkdtemp(), 'file.tar')
        extracted_dir = tempfile.mkdtemp()
        print(
            'compiled at tarfile:',
            AnnotatedIPython2CWLToolConverter(annotated_python_script).compile(
                Path(compiled_tar_file)
            ),
        )
        with tarfile.open(compiled_tar_file, 'r') as tar:
            tar.extractall(path=extracted_dir)
        print(compiled_tar_file)
        self.assertSetEqual(
            {'notebookTool', 'tool.cwl', 'Dockerfile', 'requirements.txt', 'setup.py'},
            set(os.listdir(extracted_dir)),
        )

    def test_AnnotatedIPython2CWLToolConverter_optional_arguments(self):
        annotated_python_script = os.linesep.join(
            [
                "import csv",
                "input_filename: Optional[CWLFilePathInput] = None",
                "if input_filename is None:",
                "\tinput_filename = 'data.csv'",
                "with open(input_filename) as f:",
                "\tcsv_reader = csv.reader(f)",
                "\tdata = [line for line in csv_reader]",
                "print(data)",
            ]
        )
        cwl_tool = AnnotatedIPython2CWLToolConverter(
            annotated_python_script
        ).cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}},
                'arguments': ['--'],
                'inputs': {
                    'input_filename': {
                        'type': 'File?',
                        'inputBinding': {'prefix': '--input_filename'},
                    }
                },
                'outputs': {},
            },
            cwl_tool,
        )

    def test_AnnotatedIPython2CWLToolConverter_list_arguments(self):
        annotated_python_script = os.linesep.join(
            [
                "import csv",
                "input_filename: List[CWLFilePathInput] = ['data1.csv', 'data2.csv']",
                "for fn in input_filename:",
                "\twith open(input_filename) as f:",
                "\t\tcsv_reader = csv.reader(f)",
                "\t\tdata = [line for line in csv_reader]",
                "\tprint(data)",
            ]
        )
        cwl_tool = AnnotatedIPython2CWLToolConverter(
            annotated_python_script
        ).cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}},
                'inputs': {
                    'input_filename': {
                        'type': 'File[]',
                        'inputBinding': {'prefix': '--input_filename'},
                    }
                },
                'outputs': {},
                'arguments': ['--'],
            },
            cwl_tool,
        )

    def test_AnnotatedIPython2CWLToolConverter_wrap_script_to_method(self):
        printed_message = ''
        annotated_python_script = os.linesep.join(
            [
                'global printed_message',
                f"msg: {CWLStringInput.__name__} = 'original'",
                "print('message:', msg)",
                "printed_message = msg",
            ]
        )
        exec(annotated_python_script)
        self.assertEqual('original', globals()['printed_message'])
        converter = AnnotatedIPython2CWLToolConverter(annotated_python_script)
        new_script = converter._wrap_script_to_method(
            converter._tree, converter._variables
        )
        print('\n' + new_script, '\n')
        exec(new_script)
        locals()['main']('new message')
        self.assertEqual('new message', globals()['printed_message'])

    def test_AnnotatedIPython2CWLToolConverter_wrap_script_to_method_removes_ipython2cwl_imports(
        self,
    ):
        annotated_python_scripts = [
            os.linesep.join(['import ipython2cwl', 'print("hello world")']),
            os.linesep.join(['import ipython2cwl as foo', 'print("hello world")']),
            os.linesep.join(['import ipython2cwl.iotypes', 'print("hello world")']),
            os.linesep.join(
                ['from ipython2cwl import iotypes', 'print("hello world")']
            ),
            os.linesep.join(
                [
                    'from ipython2cwl.iotypes import CWLFilePathInput',
                    'print("hello world")',
                ]
            ),
            os.linesep.join(
                [
                    'from ipython2cwl.iotypes import CWLFilePathInput, CWLBooleanInput',
                    'print("hello world")',
                ]
            ),
            os.linesep.join(['import typing, ipython2cwl', 'print("hello world")']),
        ]
        for script in annotated_python_scripts:
            conv = AnnotatedIPython2CWLToolConverter(script)
            new_script = conv._wrap_script_to_method(conv._tree, conv._variables)
            print('-' * 10)
            print(script)
            print('-' * 2)
            print(new_script)
            print('-' * 10)
            self.assertNotIn('ipython2cwl', new_script)

        self.assertIn(
            'typing',
            os.linesep.join(['import typing, ipython2cwl' 'print("hello world")']),
        )

    def test_AnnotatedIPython2CWLToolConverter_output_file_annotation(self):
        import tempfile

        root_dir = tempfile.mkdtemp()
        output_file_path = os.path.join(root_dir, "file.txt")
        annotated_python_script = os.linesep.join(
            [
                'x = "hello world"',
                f'output_path: {CWLFilePathOutput.__name__} = "{output_file_path}"',
                "with open(output_path, 'w') as f:",
                "\tf.write(x)",
            ]
        )
        converter = AnnotatedIPython2CWLToolConverter(annotated_python_script)
        new_script = converter._wrap_script_to_method(
            converter._tree, converter._variables
        )
        self.assertNotIn(CWLFilePathOutput.__name__, new_script)
        print('\n' + new_script, '\n')
        exec(new_script)
        locals()['main']()
        with open(output_file_path) as f:
            self.assertEqual("hello world", f.read())
        os.remove(output_file_path)
        tool = converter.cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}},
                'arguments': ['--'],
                'inputs': {},
                'outputs': {
                    'output_path': {
                        'type': 'File',
                        'outputBinding': {'glob': output_file_path},
                    }
                },
            },
            tool,
        )

    def test_AnnotatedIPython2CWLToolConverter_exclamation_mark_command(self):
        printed_message = ''
        annotated_python_jn_node = nbformat.from_dict(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": os.linesep.join(
                            [
                                "!ls -la\n",
                                "global printed_message\n",
                                "msg: CWLStringInput = 'original'\n",
                                "print('message:', msg)\n",
                                "printed_message = msg",
                            ]
                        ),
                    }
                ],
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3",
                    },
                    "language_info": {
                        "codemirror_mode": {"name": "ipython", "version": 3},
                        "file_extension": ".py",
                        "mimetype": "text/x-python",
                        "name": "python",
                        "nbconvert_exporter": "python",
                        "pygments_lexer": "ipython3",
                        "version": "3.6.10",
                    },
                },
                "nbformat": 4,
                "nbformat_minor": 4,
            },
        )
        converter = AnnotatedIPython2CWLToolConverter.from_jupyter_notebook_node(
            annotated_python_jn_node
        )
        new_script = converter._wrap_script_to_method(
            converter._tree, converter._variables
        )
        new_script_without_magics = os.linesep.join(
            [
                line
                for line in new_script.splitlines()
                if not line.strip().startswith('get_ipython')
            ]
        )
        print('\n' + new_script, '\n')
        exec(new_script_without_magics)

        annotated_python_jn_node.cells[0].source = os.linesep.join(
            [
                '!ls -la',
                'global printed_message',
                f'msg: {CWLStringInput.__name__} = """original\n!ls -la"""',
                "print('message:', msg)",
                "printed_message = msg",
            ]
        )
        converter = AnnotatedIPython2CWLToolConverter.from_jupyter_notebook_node(
            annotated_python_jn_node
        )
        new_script = converter._wrap_script_to_method(
            converter._tree, converter._variables
        )
        new_script_without_magics = os.linesep.join(
            [
                line
                for line in new_script.splitlines()
                if not line.strip().startswith('get_ipython')
            ]
        )
        print('\n' + new_script, '\n')
        exec(new_script_without_magics)
        locals()['main']('original\n!ls -l')
        self.assertEqual('original\n!ls -l', globals()['printed_message'])

    def test_AnnotatedIPython2CWLToolConverter_optional_array_input(self):
        s1 = os.linesep.join(
            [
                'x1: CWLBooleanInput = True',
            ]
        )
        s2 = os.linesep.join(
            [
                'x1: "CWLBooleanInput" = True',
            ]
        )
        # all variables must be the same
        self.assertEqual(
            AnnotatedIPython2CWLToolConverter(s1)._variables[0],
            AnnotatedIPython2CWLToolConverter(s2)._variables[0],
        )

        s1 = os.linesep.join(
            [
                'x1: Optional[CWLBooleanInput] = True',
            ]
        )
        s2 = os.linesep.join(
            [
                'x1: "Optional[CWLBooleanInput]" = True',
            ]
        )
        s3 = os.linesep.join(
            [
                'x1: Optional["CWLBooleanInput"] = True',
            ]
        )
        # all variables must be the same
        self.assertEqual(
            AnnotatedIPython2CWLToolConverter(s1)._variables[0],
            AnnotatedIPython2CWLToolConverter(s2)._variables[0],
        )
        self.assertEqual(
            AnnotatedIPython2CWLToolConverter(s1)._variables[0],
            AnnotatedIPython2CWLToolConverter(s3)._variables[0],
        )

        # test that does not crash
        self.assertListEqual(
            [],
            AnnotatedIPython2CWLToolConverter(
                os.linesep.join(['x1: RandomHint = True'])
            )._variables,
        )
        self.assertListEqual(
            [],
            AnnotatedIPython2CWLToolConverter(
                os.linesep.join(['x1: List[RandomHint] = True'])
            )._variables,
        )
        self.assertListEqual(
            [],
            AnnotatedIPython2CWLToolConverter(
                os.linesep.join(['x1: List["RandomHint"] = True'])
            )._variables,
        )
        self.assertListEqual(
            [],
            AnnotatedIPython2CWLToolConverter(
                os.linesep.join(['x1: "List[List[Union[RandomHint, Foo]]]" = True'])
            )._variables,
        )
        self.assertListEqual(
            [],
            AnnotatedIPython2CWLToolConverter(
                os.linesep.join(['x1: "RANDOM CHARACTERS!!!!!!" = True'])
            )._variables,
        )

    def test_AnnotatedIPython2CWLToolConverter_dumpables(self):
        script = os.linesep.join(
            [
                'message: CWLDumpableFile = "this is a text from a dumpable"',
                'message2: "CWLDumpableFile" = "this is a text from a dumpable 2"',
                'binary_message: CWLDumpableBinaryFile = b"this is a text from a binary dumpable"',
                'print("Message:", message)',
                'print(b"Binary Message:" + binary_message)',
            ]
        )
        converter = AnnotatedIPython2CWLToolConverter(script)
        generated_script = AnnotatedIPython2CWLToolConverter._wrap_script_to_method(
            converter._tree, converter._variables
        )
        for f in ['message', 'binary_message', 'message2']:
            try:
                os.remove(f)
            except FileNotFoundError:
                pass
        exec(generated_script)
        print(generated_script)
        locals()['main']()
        with open('message') as f:
            self.assertEqual('this is a text from a dumpable', f.read())
        with open('message2') as f:
            self.assertEqual('this is a text from a dumpable 2', f.read())
        with open('binary_message', 'rb') as f:
            self.assertEqual(b'this is a text from a binary dumpable', f.read())

        cwl_tool = converter.cwl_command_line_tool()
        print(cwl_tool)
        self.assertDictEqual(
            {
                'message': {'type': 'File', 'outputBinding': {'glob': 'message'}},
                'message2': {'type': 'File', 'outputBinding': {'glob': 'message2'}},
                'binary_message': {
                    'type': 'File',
                    'outputBinding': {'glob': 'binary_message'},
                },
            },
            cwl_tool['outputs'],
        )

    def test_AnnotatedIPython2CWLToolConverter_custom_dumpables(self):
        script = os.linesep.join(
            [
                'import pandas',
                'from ipython2cwl.iotypes import CWLDumpable',
                'd: CWLDumpable.dump(d.to_csv, "dumpable.csv", sep="\\t", index=False) = pandas.DataFrame([[1,2,3], [4,5,6], [7,8,9]])',
            ]
        )
        converter = AnnotatedIPython2CWLToolConverter(script)
        generated_script = AnnotatedIPython2CWLToolConverter._wrap_script_to_method(
            converter._tree, converter._variables
        )
        for f in ["dumpable.csv"]:
            try:
                os.remove(f)
            except FileNotFoundError:
                pass
        exec(generated_script)
        print(generated_script)
        locals()['main']()
        import pandas

        data_file = pandas.read_csv('dumpable.csv', sep="\t")
        self.assertListEqual(
            [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            (
                data_file.to_numpy()
                - pandas.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]]).to_numpy()
            ).tolist(),
        )

        cwl_tool = converter.cwl_command_line_tool()
        print(cwl_tool)
        self.assertDictEqual(
            {
                'd': {'type': 'File', 'outputBinding': {'glob': 'dumpable.csv'}},
            },
            cwl_tool['outputs'],
        )
        for f in ["dumpable.csv"]:
            try:
                os.remove(f)
            except FileNotFoundError:
                pass

    def test_AnnotatedIPython2CWLToolConverter_CWLPNGPlot(self):
        code = os.linesep.join(
            [
                "import matplotlib.pyplot as plt",
                "new_data: 'CWLPNGPlot' = plt.plot([1,2,3,4])",
            ]
        )
        converter = AnnotatedIPython2CWLToolConverter(code)
        new_script = converter._wrap_script_to_method(
            converter._tree, converter._variables
        )
        try:
            os.remove('new_data.png')
        except FileNotFoundError:
            pass
        exec(new_script)
        locals()['main']()
        self.assertTrue(os.path.isfile('new_data.png'))
        os.remove('new_data.png')

        tool = converter.cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}},
                'arguments': ['--'],
                'inputs': {},
                'outputs': {
                    'new_data': {
                        'type': 'File',
                        'outputBinding': {'glob': 'new_data.png'},
                    }
                },
            },
            tool,
        )

    def test_AnnotatedIPython2CWLToolConverter_CWLPNGFigure(self):
        code = os.linesep.join(
            [
                "import matplotlib.pyplot as plt",
                "new_data: 'CWLPNGFigure' = plt.plot([1,2,3,4])",
            ]
        )
        converter = AnnotatedIPython2CWLToolConverter(code)
        new_script = converter._wrap_script_to_method(
            converter._tree, converter._variables
        )
        try:
            os.remove('new_data.png')
        except FileNotFoundError:
            pass
        exec(new_script)
        locals()['main']()
        self.assertTrue(os.path.isfile('new_data.png'))
        os.remove('new_data.png')

        tool = converter.cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}},
                'arguments': ['--'],
                'inputs': {},
                'outputs': {
                    'new_data': {
                        'type': 'File',
                        'outputBinding': {'glob': 'new_data.png'},
                    }
                },
            },
            tool,
        )
