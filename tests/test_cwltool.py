from pathlib import Path
from unittest import TestCase
from ipython2cwl.cwltool import AnnotatedIPython2CWLToolConverter
import os
import tempfile
import tarfile


class TestCWLTool(TestCase):

    def test_AnnotatedIPython2CWLToolConverter_cwl_command_line_tool(self):
        annotated_python_script = os.linesep.join([
            "import csv",
            "input_filename: CWLFilePathInput = 'data.csv'",
            "flag: CWLBooleanInput = true",
            "with open(input_filename) as f:",
            "\tcsv_reader = csv.reader(f)",
            "\tdata = [line for line in reader]",
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
                    }
                },
                'outputs': [],
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
                'outputs': [],
            },
            cwl_tool
        )
