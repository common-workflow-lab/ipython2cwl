import typing


class ClickTypeAdapter:
    @classmethod
    def to_click_method(cls) -> str:
        raise NotImplementedError()


class CWLTypeAdapter:
    @classmethod
    def to_cwl(cls) -> str:
        raise NotImplementedError()


class CWLFileInput(typing.TextIO, ClickTypeAdapter):
    @classmethod
    def to_click_method(cls) -> str:
        return 'click.File('r')'

    @classmethod
    def to_cwl(cls) -> str:
        return 'File'


inputs = {CWLFileInput.__name__}
outputs = set()
