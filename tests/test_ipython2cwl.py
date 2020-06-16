import unittest
from ipython2cwl import ipython2cwl
import os


class TestIPython2CWL(unittest.TestCase):
    maxDiff = None
    tests_directory = os.path.abspath(os.path.dirname(__file__))
    jn_directory = os.sep.join([tests_directory, 'jn'])

    def test_pass_argument(self):
        output_dir = os.sep.join([self.jn_directory, 'output'])
        os.makedirs(output_dir, exist_ok=True)
        self.assertEqual(
            0,
            ipython2cwl.main(
                [
                    ipython2cwl.__file__,
                    os.sep.join([self.jn_directory, 'jn1.ipynb']),
                    '-o',
                    output_dir,
                ]
            )
        )


if __name__ == '__main__':
    unittest.main()
