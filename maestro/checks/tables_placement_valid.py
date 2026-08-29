"""'Tables placed in the wrong location' was flagged as a real Maestro failure mode, but what
counts as a valid location is not written down anywhere this harness can read (HUMAN INPUT NEEDED -
placement rules). Reports Skipped rather than guessing a rule, until
EvalConfig.table_placement carries something confirmed.
"""

from __future__ import annotations

from maestro.check_result import CheckResult, Status
from maestro.models import EvalConfig, GeneratedQuestion


def tables_placement_valid(question: GeneratedQuestion, config: EvalConfig) -> list[CheckResult]:
    if not config.table_placement.confirmed:
        return [CheckResult(
            check_name="tables_placement_valid", status=Status.SKIPPED,
            message="Placement rules are unconfirmed - see EvalConfig.table_placement.",
        )]

    return [CheckResult(
        check_name="tables_placement_valid", status=Status.FAIL,
        message="table_placement is marked confirmed but no rule is implemented yet - "
        "fill this in once the rule is known.",
    )]
