import argparse
import json
from io import StringIO
from pathlib import Path
from typing import List, Optional

import nbconvert
import nbformat

from .cwltoolextractor import AnnotatedIPython2CWLToolConverter


def jn2code(notebook):
    exporter = nbconvert.PythonExporter()
    script = exporter.from_file(StringIO(json.dumps(notebook)))
    return script


def main(argv: Optional[List[str]] = None):
    if argv is None:
        import sys
        argv = sys.argv
    parser = argparse.ArgumentParser()
    parser.add_argument('jn', type=argparse.FileType('r'), nargs=1)
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args(argv[1:])
    notebook = nbformat.read(args.jn[0], as_version=4)
    output: Path = args.output
    args.jn[0].close()
    script_code = jn2code(notebook)

    converter = AnnotatedIPython2CWLToolConverter(script_code)
    converter.compile(output)

    return 0


if __name__ == '__main__':
    main()
