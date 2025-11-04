from typing import List
import subprocess
import sys

try:
    # Python 3.8+
    from importlib import metadata
except ImportError:
    # Backport for older Python versions
    import importlib_metadata as metadata


class RequirementsManager:
    """
    That class is responsible for generating the requirements.txt file of the activated python environment.
    """

    @classmethod
    def get_all(cls) -> List[str]:
        try:
            # Use pip freeze command as the modern approach
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True
            )
            lines = result.stdout.strip().split("\n")
            return [
                line for line in lines if line and not line.startswith("ipython2cwl")
            ]
        except Exception:
            # Fallback to importlib.metadata if pip freeze fails
            try:
                # Get all installed distributions using modern importlib.metadata
                distributions = metadata.distributions()
                return [
                    f"{dist.metadata['Name']}=={dist.version}"
                    for dist in distributions
                    if dist.metadata['Name'] != "ipython2cwl"
                ]
            except Exception:
                return []
