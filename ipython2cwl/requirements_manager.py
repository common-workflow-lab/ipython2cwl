from typing import List

from pip._internal.operations import freeze


class RequirementsManager:
    """
    That class is responsible for generating the requirements.txt file of the activated python environment.
    """

    @classmethod
    def get_all(cls) -> List[str]:
        return [
            str(package.as_requirement()) for package in freeze.get_installed_distributions()
            if package.project_name != 'ipython2cwl'
        ]
