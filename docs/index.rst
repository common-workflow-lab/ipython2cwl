IPython2CWL: Convert Jupyter Notebook to CWL
================================================================================

.. image:: https://travis-ci.com/giannisdoukas/ipython2cwl.svg?branch=master
    :target: https://travis-ci.com/giannisdoukas/ipython2cwl
.. image:: https://coveralls.io/repos/github/giannisdoukas/ipython2cwl/badge.svg?branch=master
    :target: https://coveralls.io/github/giannisdoukas/ipython2cwl?branch=master


------------------------------------------------------------------------------------------

IPython2CWL is a tool for converting `IPython <https://ipython.org/>`_ Jupyter Notebooks to
`CWL <https://www.commonwl.org/>`_ Command Line Tools by simply providing typing annotation.

.. code-block:: python

    from ipython2cwl.iotypes import CWLFilePathInput, CWLFilePathOutput
    import csv
    input_filename: CWLFilePathInput = 'data.csv'
    with open(input_filename) as f:
      csv_reader = csv.reader(f)
      data = [line for line in csv_reader]
    number_of_lines = len(data)
    result_file: CWLFilePathOutput = 'number_of_lines.txt'
    with open(result_file, 'w') as f:
      f.write(str(number_of_lines))


------------------------------------------------------------------------------------------


.. toctree::
   :maxdepth: 2
   :caption: Contents:


   ipython2cwl

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
