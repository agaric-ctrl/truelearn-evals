"""Registry of the default Tier 1 checks. Importing this module eagerly imports every check
module, which makes lxml, nltk/py-readability-metrics, and pymarkdownlnt hard dependencies of
maestro.checks (and therefore maestro.runner) as a whole - not just of the specific checks that use
each one directly.
"""

from __future__ import annotations

from typing import Callable

from maestro.check_result import CheckResult
from maestro.models import EvalConfig, GeneratedQuestion

from maestro.checks.required_fields_present import required_fields_present
from maestro.checks.field_constraints import field_constraints
from maestro.checks.html_well_formed import html_well_formed
from maestro.checks.tables_no_duplicates import tables_no_duplicates
from maestro.checks.tables_placement_valid import tables_placement_valid
from maestro.checks.references_format import references_format
from maestro.checks.table_abbreviation_footnotes import table_abbreviation_footnotes
from maestro.checks.teaching_case_standard import teaching_case_standard
from maestro.checks.case_numbering import case_numbering
from maestro.checks.readability_check import readability
from maestro.checks.markdown_structural_compatibility import markdown_structural_compatibility
from maestro.checks.density_redundancy import density_redundancy
from maestro.checks.arrow_style import arrow_style

CheckFunction = Callable[[GeneratedQuestion, EvalConfig], list[CheckResult]]

DEFAULT_CHECKS: list[CheckFunction] = [
    required_fields_present,
    field_constraints,
    html_well_formed,
    tables_no_duplicates,
    tables_placement_valid,
    references_format,
    table_abbreviation_footnotes,
    teaching_case_standard,
    case_numbering,
    readability,
    markdown_structural_compatibility,
    density_redundancy,
    arrow_style,
]
