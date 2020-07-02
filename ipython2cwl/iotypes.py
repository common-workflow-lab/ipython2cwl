from typing import Callable


class _CWLInput:
    pass


class CWLFilePathInput(str, _CWLInput):
    pass


class CWLBooleanInput(_CWLInput):
    pass


class CWLStringInput(str, _CWLInput):
    pass


class CWLIntInput(_CWLInput):
    pass


class _CWLOutput:
    pass


class CWLFilePathOutput(str, _CWLOutput):
    pass


class CWLDumpable(_CWLOutput):

    @classmethod
    def dump(cls, dumper: Callable, *args, **kwargs):
        return _CWLOutput


class CWLDumpableFile(CWLDumpable):
    pass


class CWLDumpableBinaryFile(CWLDumpable):
    pass
