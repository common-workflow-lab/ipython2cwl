# IPython2CWL

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/ed284fda44ca4398a6f26d496662eae2)](https://app.codacy.com/manual/giannisdoukas/ipython2cwl?utm_source=github.com&utm_medium=referral&utm_content=giannisdoukas/ipython2cwl&utm_campaign=Badge_Grade_Dashboard)
[![Build Status](https://travis-ci.com/giannisdoukas/ipython2cwl.svg?branch=master)](https://travis-ci.com/giannisdoukas/ipython2cwl)
[![Coverage Status](https://coveralls.io/repos/github/giannisdoukas/ipython2cwl/badge.svg?branch=master)](https://coveralls.io/github/giannisdoukas/ipython2cwl?branch=master)
[![Documentation Status](https://readthedocs.org/projects/ipython2cwl/badge/?version=latest)](https://ipython2cwl.readthedocs.io/en/latest/?badge=latest)
[![Downloads](https://pepy.tech/badge/ipython2cwl/month)](https://pepy.tech/project/ipython2cwl/month)

IPython2CWL is a tool for converting [IPython](https://ipython.org/) Jupyter Notebooks to
[CWL (Common Workflow Language)](https://www.commonwl.org/) Command Line Tools by simply providing typing annotation.


```python
from ipython2cwl.iotypes import CWLFilePathInput, CWLFilePathOutput
import csv
input_filename: 'CWLFilePathInput' = 'data.csv'
with open(input_filename) as f:
  csv_reader = csv.reader(f)
  data = [line for line in csv_reader]
number_of_lines = len(data)
result_file: 'CWLFilePathOutput' = 'number_of_lines.txt'
with open(result_file, 'w') as f:
  f.write(str(number_of_lines))
```

IPython2CWL is based on [repo2docker](https://github.com/jupyter/repo2docker), the same tool
used by [mybinder](https://mybinder.org/). Now, by writing Jupyter Notebook and publishing them, including repo2docker
configuration, the community can not only execute the notebooks remotely but also to use them as steps in scientific
workflows.


## Install

```
pip install ipython2cwl
```

### Example
 
```
jupyter repo2cwl https://github.com/giannisdoukas/cwl-annotated-jupyter-notebook.git -o .
```

### Docs

[https://ipython2cwl.readthedocs.io/](https://ipython2cwl.readthedocs.io/en/latest/)

### Demo

[https://github.com/giannisdoukas/ipython2cwl-demo](https://github.com/giannisdoukas/ipython2cwl-demo)