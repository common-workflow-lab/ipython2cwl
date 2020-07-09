"""

Basic Data Types
^^^^^^^^^^^^^^^^^

Each variable can be an input or an output. The basic data types are:

* Inputs:

  * CWLFilePathInput

  * CWLBooleanInput

  * CWLStringInput

  * CWLIntInput

* Outputs:

  * CWLFilePathOutput

  * CWLDumpableFile

  * CWLDumpableBinaryFile


Complex Dumpables Types
^^^^^^^^^^^^^^^^^^^^^^^^

Dumpables are variables which are able to be written to a file, but the jupyter notebook developer
does not want to write it, for example to avoid the IO overhead. To bypass that, you can use
Dumpables annotation. See :func:`~iotypes.CWLDumpable.dump` for more details.

"""
from typing import Callable


class _CWLInput:
    pass


class CWLFilePathInput(str, _CWLInput):
    """Use that hint to annotate that a variable is a string-path input. You can use the typing annotation
    as a string by importing it. At the generated script a command line argument with the name of the variable
    will be created and the assignment of value will be generalised.

    >>> dataset1: CWLFilePathInput = './data/data.csv'
    >>> dataset2: 'CWLFilePathInput' = './data/data.csv'

    """
    pass


class CWLBooleanInput(_CWLInput):
    """Use that hint to annotate that a variable is a boolean input. You can use the typing annotation
    as a string by importing it. At the generated script a command line argument with the name of the variable
    will be created and the assignment of value will be generalised.

    >>> dataset1: CWLBooleanInput = True
    >>> dataset2: 'CWLBooleanInput' = False

    """
    pass


class CWLStringInput(str, _CWLInput):
    """Use that hint to annotate that a variable is a string input. You can use the typing annotation
        as a string by importing it. At the generated script a command line argument with the name of the variable
        will be created and the assignment of value will be generalised.

        >>> dataset1: CWLBooleanInput = 'this is a message input'
        >>> dataset2: 'CWLBooleanInput' = 'yet another message input'

        """
    pass


class CWLIntInput(_CWLInput):
    """Use that hint to annotate that a variable is a integer input. You can use the typing annotation
    as a string by importing it. At the generated script a command line argument with the name of the variable
    will be created and the assignment of value will be generalised.

    >>> dataset1: CWLBooleanInput = 1
    >>> dataset2: 'CWLBooleanInput' = 2

    """
    pass


class _CWLOutput:
    pass


class CWLFilePathOutput(str, _CWLOutput):
    """Use that hint to annotate that a variable is a string-path to an output file. You can use the typing annotation
    as a string by importing it. The generated file will be mapped as a CWL output.

    >>> filename: CWLBooleanInput = 'data.csv'

    """
    pass


class CWLDumpable(_CWLOutput):
    """Use that class to define custom Dumpables variables."""

    @classmethod
    def dump(cls, dumper: Callable, filename, *args, **kwargs):
        """
        Set the function to be used to dump the variable to a file.

        >>> import pandas
        >>> d: CWLDumpable.dump(d.to_csv, "dumpable.csv", sep="\\t", index=False) = pandas.DataFrame(
        ...     [[1,2,3], [4,5,6], [7,8,9]]
        ... )

        In that example the converter will add at the end of the script the following line:
        >>> d.to_csv("dumpable.csv", sep="\\t", index=False)

        :param dumper: The function that has to be called to write the variable to a file.
        :param filename: The name of the generated file. That string must be the first argument
                        in the dumper function. That file will also be mapped as an output in
                        the CWL file.
        :param args: Any positional arguments you want to pass to dumper after the filename
        :param kwargs: Any keyword arguments you want to pass to dumper
        """
        return _CWLOutput


class CWLDumpableFile(CWLDumpable):
    """Use that annotation to define that a variable should be dumped to a text file. For example for the annotation:

    >>> data: CWLDumpableFile = "this is text data"


    the converter will append at the end of the script the following lines:


    >>> with open('data', 'w') as f:
    ...     f.write(data)


    and at the CWL, the data, will be mapped as a output.
    """
    pass


class CWLDumpableBinaryFile(CWLDumpable):
    """Use that annotation to define that a variable should be dumped to a binary file. For example for the annotation:

    >>> data: CWLDumpableBinaryFile = b"this is text data"

    the converter will append at the end of the script the following lines:

    >>> with open('data', 'wb') as f:
    ...     f.write(data)

    and at the CWL, the data, will be mapped as a output.
    """
    pass


class CWLPNGPlot(CWLDumpable):
    """Use that annotation to define that after the assigment of that variable the plt.savefig() should
    be called.

    >>> import matplotlib.pyplot as plt
    >>> data = [1,2,3]
    >>> new_data: 'CWLPNGPlot' = plt.plot(data)

    the converter will tranform these lines to

    >>> import matplotlib.pyplot as plt
    >>> data = [1,2,3]
    >>> new_data: 'CWLPNGPlot' = plt.plot(data)
    >>> plt.savefig('new_data.png')


    Note that by default if you have multiple plot statements in the same notebook will be written
    in the same file. If you want to write them in separates you have to do it in separate figures.
    To do that in your notebook you have to create a new figure before the plot command or use the CWLPNGFigure.

    >>> import matplotlib.pyplot as plt
    >>> data = [1,2,3]
    >>> plt.figure()
    >>> new_data: 'CWLPNGPlot' = plt.plot(data)
    """
    pass


class CWLPNGFigure(CWLDumpable):
    """The same with :class:`~ipython2cwl.iotypes.CWLPNGPlot` but creates new figures before plotting. Use that
    annotation of you don't want to write multiple graphs in the same image

    >>> import matplotlib.pyplot as plt
    >>> data = [1,2,3]
    >>> new_data: 'CWLPNGPlot' = plt.plot(data)

    the converter will tranform these lines to

    >>> import matplotlib.pyplot as plt
    >>> data = [1,2,3]
    >>> plt.figure()
    >>> new_data: 'CWLPNGPlot' = plt.plot(data)
    >>> plt.savefig('new_data.png')

    """
