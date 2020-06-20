import typing


class ClickTypeAdapter:
    @classmethod
    def to_click_method(cls) -> str:
        raise NotImplementedError()


class CWLTypeAdapter:
    @classmethod
    def to_cwl(cls) -> str:
        raise NotImplementedError()


class CWLFilePathInput(typing.TextIO, ClickTypeAdapter):
    @classmethod
    def to_click_method(cls) -> str:
        return 'click.Path(exists=True, file_okay=True, dir_okay=False, writable=False, readable=True)'

    @classmethod
    def to_cwl(cls) -> str:
        return 'File'


inputs = {CWLFilePathInput.__name__}
outputs = set()
