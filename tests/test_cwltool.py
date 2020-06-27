import os
import tarfile
import tempfile
from pathlib import Path
from unittest import TestCase

from ipython2cwl.cwltoolextractor import AnnotatedIPython2CWLToolConverter
from ipython2cwl.iotypes import CWLStringInput, CWLFilePathOutput


class TestCWLTool(TestCase):
    maxDiff = None

    def test_AnnotatedIPython2CWLToolConverter_cwl_command_line_tool(self):
        annotated_python_script = os.linesep.join([
            "import csv",
            "input_filename: CWLFilePathInput = 'data.csv'",
            "flag: CWLBooleanInput = true",
            "num: CWLIntInput = 1",
            "msg: CWLStringInput = 'hello world'",
            "with open(input_filename) as f:",
            "\tcsv_reader = csv.reader(f)",
            "\tdata = [line for line in reader]",
            "print(msg)",
            "print(num)",
            "print(flag)",
        ])

        cwl_tool = AnnotatedIPython2CWLToolConverter(annotated_python_script).cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {
                    'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}
                },
                'inputs': {
                    'input_filename': {
                        'type': 'File',
                        'inputBinding': {
                            'prefix': '--input_filename'
                        }
                    },
                    'flag': {
                        'type': 'boolean',
                        'inputBinding': {
                            'prefix': '--flag'
                        }
                    },
                    'num': {
                        'type': 'int',
                        'inputBinding': {
                            'prefix': '--num'
                        }
                    },
                    'msg': {
                        'type': 'string',
                        'inputBinding': {
                            'prefix': '--msg'
                        }
                    },
                },
                'outputs': {},
            },
            cwl_tool
        )

    def test_AnnotatedIPython2CWLToolConverter_compile(self):
        annotated_python_script = os.linesep.join([
            "import csv",
            "input_filename: CWLFilePathInput = 'data.csv'",
            "with open(input_filename) as f:",
            "\tcsv_reader = csv.reader(f)",
            "\tdata = [line for line in csv_reader]",
            "print(data)"
        ])
        compiled_tar_file = os.path.join(tempfile.mkdtemp(), 'file.tar')
        extracted_dir = tempfile.mkdtemp()
        print('compiled at tarfile:',
              AnnotatedIPython2CWLToolConverter(annotated_python_script)
              .compile(Path(compiled_tar_file)))
        with tarfile.open(compiled_tar_file, 'r') as tar:
            tar.extractall(path=extracted_dir)
        print(compiled_tar_file)
        self.assertSetEqual(
            {'notebookTool', 'tool.cwl', 'Dockerfile', 'requirements.txt', 'setup.py'},
            set(os.listdir(extracted_dir))
        )

    def test_AnnotatedIPython2CWLToolConverter_optional_arguments(self):
        annotated_python_script = os.linesep.join([
            "import csv",
            "input_filename: Optional[CWLFilePathInput] = None",
            "if input_filename is None:",
            "\tinput_filename = 'data.csv'",
            "with open(input_filename) as f:",
            "\tcsv_reader = csv.reader(f)",
            "\tdata = [line for line in csv_reader]",
            "print(data)"
        ])
        cwl_tool = AnnotatedIPython2CWLToolConverter(annotated_python_script).cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {
                    'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}
                },
                'inputs': {
                    'input_filename': {
                        'type': 'File?',
                        'inputBinding': {
                            'prefix': '--input_filename'
                        }
                    }
                },
                'outputs': {},
            },
            cwl_tool
        )

    def test_AnnotatedIPython2CWLToolConverter_list_arguments(self):
        annotated_python_script = os.linesep.join([
            "import csv",
            "input_filename: List[CWLFilePathInput] = ['data1.csv', 'data2.csv']",
            "for fn in input_filename:",
            "\twith open(input_filename) as f:",
            "\t\tcsv_reader = csv.reader(f)",
            "\t\tdata = [line for line in csv_reader]",
            "\tprint(data)"
        ])
        cwl_tool = AnnotatedIPython2CWLToolConverter(annotated_python_script).cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'notebookTool',
                'hints': {
                    'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}
                },
                'inputs': {
                    'input_filename': {
                        'type': 'File[]',
                        'inputBinding': {
                            'prefix': '--input_filename'
                        }
                    }
                },
                'outputs': {},
            },
            cwl_tool
        )

    def test_AnnotatedIPython2CWLToolConverter_wrap_script_to_method(self):
        printed_message = ''
        annotated_python_script = os.linesep.join([
            'global printed_message',
            f"msg: {CWLStringInput.__name__} = 'original'",
            "print('message:', msg)",
            "printed_message = msg"
        ])
        exec(annotated_python_script)
        self.assertEqual('original', globals()['printed_message'])
        converter = AnnotatedIPython2CWLToolConverter(annotated_python_script)
        new_script = converter._wrap_script_to_method(converter._tree, converter._variables)
        print('\n' + new_script, '\n')
        exec(new_script)
        locals()['main']('new message')
        self.assertEqual('new message', globals()['printed_message'])

    def test_AnnotatedIPython2CWLToolConverter_wrap_script_to_method_removes_ipython2cwl_imports(self):
        annotated_python_scripts = [
            os.linesep.join([
                'import ipython2cwl',
                'print("hello world")'
            ]),
            os.linesep.join([
                'import ipython2cwl as foo',
                'print("hello world")'
            ]),
            os.linesep.join([
                'import ipython2cwl.iotypes',
                'print("hello world")'
            ]),
            os.linesep.join([
                'from ipython2cwl import iotypes',
                'print("hello world")'
            ]),
            os.linesep.join([
                'from ipython2cwl.iotypes import CWLFilePathInput',
                'print("hello world")'
            ]),
            os.linesep.join([
                'from ipython2cwl.iotypes import CWLFilePathInput, CWLBooleanInput',
                'print("hello world")'
            ]),
            os.linesep.join([
                'import typing, ipython2cwl',
                'print("hello world")'
            ])
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

        self.assertIn('typing', os.linesep.join([
            'import typing, ipython2cwl'
            'print("hello world")'
        ]))

    def test_AnnotatedIPython2CWLToolConverter_output_file_annotation(self):
        import tempfile
        root_dir = tempfile.mkdtemp()
        output_file_path = os.path.join(root_dir, "file.txt")
        annotated_python_script = os.linesep.join([
            'x = "hello world"',
            f'output_path: {CWLFilePathOutput.__name__} = "{output_file_path}"',
            "with open(output_path, 'w') as f:",
            "\tf.write(x)"
        ])
        converter = AnnotatedIPython2CWLToolConverter(annotated_python_script)
        new_script = converter._wrap_script_to_method(converter._tree, converter._variables)
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
                'hints': {
                    'DockerRequirement': {'dockerImageId': 'jn2cwl:latest'}
                },
                'inputs': {},
                'outputs': {
                    'output_path': {
                        'type': 'File',
                        'outputBinding': {
                            'glob': output_file_path
                        }
                    }
                },
            },
            tool
        )

    # def test_AnnotatedIPython2CWLToolConverter_exclamation_mark_command(self):
    #     printed_message = ''
    #     annotated_python_script = os.linesep.join([
    #         '!ls -la',
    #         'global printed_message',
    #         f"msg: {CWLStringInput.__name__} = 'original'",
    #         "print('message:', msg)",
    #         "printed_message = msg"
    #     ])
    #     exec(annotated_python_script)
    #     self.assertEqual('original', globals()['printed_message'])
    #     converter = AnnotatedIPython2CWLToolConverter(annotated_python_script)
    #     new_script = converter._wrap_script_to_method(converter._tree, converter._variables)
    #     print('\n' + new_script, '\n')
    #     exec(new_script)
    #     locals()['main']('new message')
    #     self.assertEqual('new message', globals()['printed_message'])
