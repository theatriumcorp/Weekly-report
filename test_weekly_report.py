import pytest
from weekly_report import generate_weekly_report, ATRIUM_CONSTRUCTION_CONTEXT


def test_atrium_context_contains_required_fields():
    """Verify the Atrium construction context has all required data."""
    assert "Atrium Construction" in ATRIUM_CONSTRUCTION_CONTEXT
    assert "Active Projects" in ATRIUM_CONSTRUCTION_CONTEXT
    assert "Budget Summary" in ATRIUM_CONSTRUCTION_CONTEXT
    assert "Issues & Risks" in ATRIUM_CONSTRUCTION_CONTEXT


def test_weekly_report_is_generated():
    """Generate the weekly report and display it."""
    report = generate_weekly_report()

    print("\n" + "=" * 60)
    print("   ATRIUM CONSTRUCTION — WEEKLY REPORT")
    print("=" * 60)
    print(report)
    print("=" * 60 + "\n")

    assert isinstance(report, str)
    assert len(report) > 100, "Report should have substantial content"


def test_weekly_report_covers_key_sections():
    """Verify the report includes expected sections."""
    report = generate_weekly_report()

    report_lower = report.lower()
    assert any(word in report_lower for word in ["summary", "overview", "status"]), \
        "Report should include a summary/overview section"
    assert any(word in report_lower for word in ["risk", "issue", "concern", "challenge"]), \
        "Report should address risks or issues"
    assert any(word in report_lower for word in ["next", "priority", "upcoming", "week"]), \
        "Report should include next steps or priorities"
