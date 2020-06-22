import codecs
import os.path

from setuptools import setup
from setuptools import find_packages

name = 'ipython2cwl'


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


with open(os.sep.join([os.path.abspath(os.path.dirname(__file__)), "README.md"]), "r") as fh:
    long_description = fh.read()

setup(
    name=name,
    version=get_version(f"{name}/__init__.py"),
    packages=['ipython2cwl'],
    package_dir={'ipython2cwl': 'ipython2cwl'},
    package_data={'ipython2cwl': ['ipython2cwl/templates/*']},
    author='Yannis Doukas',
    author_email='giannisdoukas2311@gmail.com',
    description='Convert IPython Jupyter Notebooks to CWL tool',
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires='>=3.6',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
        "Development Status :: 2 - Pre-Alpha",
        "Framework :: IPython",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    entry_points={
        'console_scripts': [
            'jupyter-jn2cwl=ipython2cwl.ipython2cwl:main',
        ],
    },
    install_requires=[
        'nbformat>=5.0.6',
        'astor>=0.8.1',
        'PyYAML>=5.3.1'
    ],
    test_suite='tests',
)
