import argparse
import os
from pathlib import Path
from typing import List, Optional

import nbformat
from pip._internal.operations import freeze

with open(os.sep.join([os.path.abspath(os.path.dirname(__file__)), 'template.dockerfile'])) as f:
    DOCKERFILE_TEMPLATE = f.read()


def directory_type(directory_argument: str):
    """Function to be used as a directory type for argparse argument."""
    directory = Path(directory_argument)
    if not directory.is_dir():
        raise RuntimeError('directory does not exists')
    return str(directory.absolute())


def main(argv: Optional[List[str]] = None):
    if argv is None:
        import sys
        argv = sys.argv
    parser = argparse.ArgumentParser()
    parser.add_argument('jn', type=argparse.FileType('r'), nargs=1)
    parser.add_argument('-o', '--output-dir', type=directory_type, required=True)
    args = parser.parse_args(argv[1:])
    notebook = nbformat.read(args.jn[0], as_version=4)
    output_dir = args.output_dir
    args.jn[0].close()
    script_code = '\n'.join(
        [f"\n\n# --------- cell - {i} ---------\n\n{cell.source}" for i, cell in
         enumerate(filter(lambda c: c.cell_type == 'code', notebook.cells), start=1)]
    )
    print(script_code)
    requirements = list(freeze.freeze())
    with open(os.sep.join([output_dir, 'app.py']), 'w') as f:
        f.write(script_code)
    with open(os.sep.join([output_dir, 'requirements.txt']), 'w') as f:
        f.write('\n'.join(requirements))
    with open(os.sep.join([output_dir, 'Dockerfile']), 'w') as f:
        f.write(
            DOCKERFILE_TEMPLATE.format(
                python_version=notebook.metadata.language_info.version,
                source_code_directory=output_dir
            )
        )
    return 0


if __name__ == '__main__':
    main()
