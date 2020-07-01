class _CWLInput:
    pass


class CWLFilePathInput(_CWLInput):
    pass


class CWLBooleanInput(_CWLInput):
    pass


class CWLStringInput(_CWLInput):
    pass


class CWLIntInput(_CWLInput):
    pass


class _CWLOutput:
    pass


class CWLFilePathOutput(_CWLOutput):
    pass


class _CWLDumpable(_CWLOutput):
    pass


class CWLDumpableFile(_CWLDumpable):
    pass


class CWLDumpableBinaryFile(_CWLDumpable):
    pass
