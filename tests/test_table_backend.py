"""Tests for pbi_cli.core.tom_backend table_update."""

from __future__ import annotations

import pytest

from pbi_cli.core.tom_backend import table_update


def _get_table(model):
    """Find the single table in the mock model."""
    return next(t for t in model.Tables)


# ---------------------------------------------------------------------------
# table_update
# ---------------------------------------------------------------------------


class TestTableUpdate:
    def test_description_only(self, mock_session) -> None:
        model = mock_session.model
        table = _get_table(model)

        result = table_update(model, "Sales", description="Revenue fact")

        assert result == {"status": "updated", "name": "Sales", "changed": ["description"]}
        assert table.Description == "Revenue fact"
        assert table.IsHidden is False  # untouched

    def test_hidden_only(self, mock_session) -> None:
        model = mock_session.model
        table = _get_table(model)

        result = table_update(model, "Sales", is_hidden=True)

        assert result["changed"] == ["isHidden"]
        assert table.IsHidden is True
        assert table.Description == ""  # untouched

    def test_visible_unhides(self, mock_session) -> None:
        model = mock_session.model
        table = _get_table(model)
        table.IsHidden = True

        result = table_update(model, "Sales", is_hidden=False)

        assert result["changed"] == ["isHidden"]
        assert table.IsHidden is False

    def test_both_description_and_hidden(self, mock_session) -> None:
        model = mock_session.model
        table = _get_table(model)

        result = table_update(model, "Sales", description="Bridge", is_hidden=True)

        assert result["changed"] == ["description", "isHidden"]
        assert table.Description == "Bridge"
        assert table.IsHidden is True

    def test_no_changes_returns_unchanged(self, mock_session) -> None:
        model = mock_session.model
        table = _get_table(model)
        table.Description = "Keep me"
        table.IsHidden = True

        result = table_update(model, "Sales")

        assert result == {"status": "unchanged", "name": "Sales", "changed": []}
        # Nothing mutated
        assert table.Description == "Keep me"
        assert table.IsHidden is True

    def test_table_not_found(self, mock_session) -> None:
        model = mock_session.model

        with pytest.raises(ValueError, match="not found"):
            table_update(model, "DoesNotExist", description="x")
