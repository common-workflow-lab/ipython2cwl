import argparse
import os
import stat
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from urllib.parse import urlparse

import nbformat
from git import Repo
from repo2docker import Repo2Docker

from .cwltool import AnnotatedIPython2CWLToolConverter
from .ipython2cwl import jn2code


def main(argv: Optional[List[str]] = None):
    if argv is None:
        import sys
        argv = sys.argv
    parser = argparse.ArgumentParser()
    parser.add_argument('repo', type=urlparse, nargs=1)
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args(argv[1:])

    notebook = nbformat.read(args.jn[0], as_version=4)
    output: Path = args.output
    args.jn[0].close()
    script_code = '\n'.join(
        [f"\n\n# --------- cell - {i} ---------\n\n{cell.source}" for i, cell in
         enumerate(filter(lambda c: c.cell_type == 'code', notebook.cells), start=1)]
    )

    converter = AnnotatedIPython2CWLToolConverter(script_code)
    converter.compile(output)

    return 0


def repo2cwl(git_directory_path: Repo) -> Tuple[str, List[Dict]]:
    """
    Takes an original
    :param git_directory_path:
    :return: The generated build image id & the cwl description
    """
    r2d = Repo2Docker()
    r2d.target_repo_dir = os.path.join(os.path.sep, 'app')
    r2d.repo = git_directory_path.tree().abspath
    bin_path = os.path.join(r2d.repo, 'cwl', 'bin')
    os.makedirs(bin_path, exist_ok=True)
    notebooks_paths = []
    for path, subdirs, files in os.walk(r2d.repo):
        for name in files:
            if name.endswith('.ipynb'):
                notebooks_paths.append(os.path.join(path, name))

    tools = []
    for notebook in notebooks_paths:
        with open(notebook) as fd:
            code = jn2code(nbformat.read(fd, as_version=4))

        converter = AnnotatedIPython2CWLToolConverter(code)

        script_name = os.path.basename(notebook)[:-6]
        new_script_path = os.path.join(bin_path, script_name)
        script = os.linesep.join([
            '#!/usr/bin/env python',
            converter._wrap_script_to_method(converter._tree, converter._variables)
        ])
        with open(new_script_path, 'w') as fd:
            fd.write(script)
        tool = converter.cwl_command_line_tool(r2d.output_image_spec)
        in_git_dir_script_file = os.path.join(bin_path, script_name)
        tool_st = os.stat(in_git_dir_script_file)
        os.chmod(in_git_dir_script_file, tool_st.st_mode | stat.S_IEXEC)

        tool['baseCommand'] = os.path.join('/app', 'cwl', 'bin', script_name)
        tools.append(tool)
    git_directory_path.index.commit("auto-commit")

    r2d.build()
    # fix dockerImageId
    for tool in tools:
        tool['hints']['DockerRequirement']['dockerImageId'] = r2d.output_image_spec
    return r2d.output_image_spec, tools


if __name__ == '__main__':
    main()
