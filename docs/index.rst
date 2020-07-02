IPython2CWL: Convert Jupyter Notebook to CWL
================================================================================

.. image:: https://travis-ci.com/giannisdoukas/ipython2cwl.svg?branch=master
    :target: https://travis-ci.com/giannisdoukas/ipython2cwl
.. image:: https://coveralls.io/repos/github/giannisdoukas/ipython2cwl/badge.svg?branch=master
    :target: https://coveralls.io/github/giannisdoukas/ipython2cwl?branch=master
.. image:: https://pepy.tech/badge/ipython2cwl/month
    :target: https://github.com/giannisdoukas/ipython2cwl

------------------------------------------------------------------------------------------

IPython2CWL is a tool for converting `IPython <https://ipython.org/>`_ Jupyter Notebooks to
`CWL <https://www.commonwl.org/>`_ Command Line Tools by simply providing typing annotation.

.. code-block:: python

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


------------------------------------------------------------------------------------------

IPython2CWL is based on `repo2docker <https://github.com/jupyter/repo2docker>`_, the same tool
used by `mybinder <https://mybinder.org/>`_. Now, by writing Jupyter Notebook and publishing them, including repo2docker
configuration, the community can not only execute the notebooks remotely but can also use them as steps in scientific
workflows.

* `Install ipython2cwl <https://pypi.org/project/ipython2cwl/>`_: :code:`pip install ipython2cwl`
* Ensure that you have docker running
* Create a directory to store the generated cwl files, for example cwlbuild
* Execute :code:`jupyter repo2cwl https://github.com/giannisdoukas/cwl-annotated-jupyter-notebook.git -o cwlbuild`

HOW IT WORKS?
------------------

IPython2CWL parses each IPython notebook and finds the variables with the typing annotations. For each input variable,
the assigment of that variable will be generalised as a command line argument. Each output variable will be mapped
in the cwl description as an output file.

SUPPORTED TYPES
------------------

.. automodule:: ipython2cwl.iotypes
   :members:


THAT'S COOL! WHAT ABOUT LIST & OPTIONAL ARGUMENTS?
"""""""""""""""""""""""""""""""""""""""""""""""""""

The basic input data types can be combined with the List and Optional annotations. For example, write the following
annotation:

.. code-block:: python

  file_inputs: List[CWLFilePathInput] = ['data1.txt', 'data2.txt', 'data3.txt']
  example: Optional[CWLStringInput] = None


SEEMS INTERESTING! WHAT ABOUT A DEMO?
----------------------------------------

If you would like to see a demo before you want to start annotating your notebooks check here!
`github.com/giannisdoukas/ipython2cwl-demo <https://github.com/giannisdoukas/ipython2cwl-demo>`_


WHAT IF I WANT TO VALIDATE THAT THE GENERATED SCRIPTS ARE CORRECT?
------------------------------------------------------------------

All the generated scripts are stored in the docker image under the directory :code:`/app/cwl/bin`. You can see the list
of the files by running :code:`docker run [IMAGE_ID] find /app/cwl/bin/ -type f`.



