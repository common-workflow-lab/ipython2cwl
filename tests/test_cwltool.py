from unittest import TestCase
from ipython2cwl.cwltool import AnnotatedIPython2CWLToolConverter
import os


class TestCWLTool(TestCase):

    def test_AnnotatedIPython2CWLToolConverter_cwl_command_line_tool(self):
        annotated_python_script = os.linesep.join([
            "import csv",
            "input_filename: CWLFileInput = 'data.csv'",
            "with open(input_filename) as f:",
            "\tcsv_reader = csv.reader(f)",
            "\tdata = [line for line in reader]",
        ])

        cwl_tool = AnnotatedIPython2CWLToolConverter(annotated_python_script).cwl_command_line_tool()
        self.assertDictEqual(
            {
                'cwlVersion': "v1.1",
                'class': 'CommandLineTool',
                'baseCommand': 'python',
                'arguments': [{'position': 0, 'valueFrom': 'tool.py'}],
                'inputs': [{
                    'input_filename': {
                        'type': 'File',
                        'inputBinding': {
                            'prefix': '--input_filename'
                        }
                    }
                }],
                'outputs': [],
            },
            cwl_tool
        )
