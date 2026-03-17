"""Ground truth generation for query validation."""

from typing import List
from ...models.artifacts import PRRecord, DiffPatch


class GroundTruthGenerator:
    """Generates ground truth patches for validation."""

    def generate_cumulative_patch(self, pr_records: List[PRRecord]) -> str:
        """
        Generate cumulative patch from all PRs in chain.

        Args:
            pr_records: List of PR records

        Returns:
            Cumulative patch string
        """
        if not pr_records:
            return ""

        # Combine all patches
        all_patches = []
        for pr in pr_records:
            for patch in pr.patches:
                all_patches.append(f"--- a/{patch.path}\n+++ b/{patch.path}\n{patch.patch}")

        return "\n\n".join(all_patches)

    def generate_pr_patch(self, pr: PRRecord) -> str:
        """
        Generate patch for a single PR.

        Args:
            pr: PR record

        Returns:
            Patch string
        """
        if not pr.patches:
            return ""

        patches = []
        for patch in pr.patches:
            patches.append(f"--- a/{patch.path}\n+++ b/{patch.path}\n{patch.patch}")

        return "\n\n".join(patches)

    def generate_validation_criteria(self, pr: PRRecord) -> List[str]:
        """
        Generate validation criteria for a PR.

        Args:
            pr: PR record

        Returns:
            List of validation criteria
        """
        criteria = []

        # File-based criteria
        if pr.files_changed:
            criteria.append(f"Modified files: {', '.join(pr.files_changed[:3])}")

        # Function type based criteria
        from ...utils.text_utils import infer_function_type
        func_type = infer_function_type(pr.title, pr.labels)

        if func_type == "BUG":
            criteria.append("Bug is fixed and regression test is added")
        elif func_type == "ENH":
            criteria.append("New functionality works as described")
        elif func_type == "DOC":
            criteria.append("Documentation is clear and accurate")
        elif func_type == "TST":
            criteria.append("Tests pass and provide adequate coverage")

        # General criteria
        criteria.append("Existing tests continue to pass")
        criteria.append("Code follows project conventions")

        return criteria
