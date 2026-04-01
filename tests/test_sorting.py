"""
Tests for netmon.ui.sorting

Covered scenarios:
- SortState initial state
- apply(): new column sets it with ascending=True
- apply(): same column toggles direction
- reset(): restores default state
- is_active: reflects whether a column is selected
- column_name(): returns display name of active column
- arrow(): returns correct symbol for direction
- SORT_COLUMNS structure: 6 entries, each with attribute name and display name
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/home/lice/hdd/Projects/netmon")

from netmon.ui.sorting import SORT_COLUMNS, SortState


class TestSortStateInitial:
    def test_column_is_none_by_default(self):
        state = SortState()
        assert state.column is None

    def test_ascending_is_true_by_default(self):
        state = SortState()
        assert state.ascending is True

    def test_is_not_active_by_default(self):
        state = SortState()
        assert state.is_active is False


class TestSortStateApply:
    def test_apply_new_column_sets_column(self):
        state = SortState()
        state.apply(1)
        assert state.column == 1

    def test_apply_new_column_sets_ascending(self):
        state = SortState()
        state.apply(3)
        assert state.ascending is True

    def test_apply_new_column_makes_active(self):
        state = SortState()
        state.apply(2)
        assert state.is_active is True

    def test_apply_same_column_toggles_to_descending(self):
        state = SortState()
        state.apply(1)
        state.apply(1)
        assert state.ascending is False

    def test_apply_same_column_twice_toggles_back_to_ascending(self):
        state = SortState()
        state.apply(1)
        state.apply(1)
        state.apply(1)
        assert state.ascending is True

    def test_apply_different_column_resets_to_ascending(self):
        state = SortState()
        state.apply(1)
        state.apply(1)  # now descending
        state.apply(2)  # new column → back to ascending
        assert state.ascending is True
        assert state.column == 2

    def test_apply_all_six_columns(self):
        for col in range(1, 7):
            state = SortState()
            state.apply(col)
            assert state.column == col


class TestSortStateReset:
    def test_reset_clears_column(self):
        state = SortState()
        state.apply(4)
        state.reset()
        assert state.column is None

    def test_reset_restores_ascending(self):
        state = SortState()
        state.apply(4)
        state.apply(4)  # descending
        state.reset()
        assert state.ascending is True

    def test_reset_makes_inactive(self):
        state = SortState()
        state.apply(2)
        state.reset()
        assert state.is_active is False


class TestSortStateColumnName:
    def test_column_name_returns_empty_when_inactive(self):
        state = SortState()
        assert state.column_name() == ""

    def test_column_name_matches_sort_columns(self):
        for col_num, (_, display_name) in enumerate(SORT_COLUMNS, start=1):
            state = SortState()
            state.apply(col_num)
            assert state.column_name() == display_name

    def test_column_name_all_six(self):
        expected_names = [name for _, name in SORT_COLUMNS]
        for idx, expected in enumerate(expected_names, start=1):
            state = SortState()
            state.apply(idx)
            assert state.column_name() == expected


class TestSortStateArrow:
    def test_arrow_ascending_is_up(self):
        state = SortState()
        assert state.arrow() == "▲"

    def test_arrow_descending_is_down(self):
        state = SortState()
        state.apply(1)
        state.apply(1)  # toggle to descending
        assert state.arrow() == "▼"

    def test_arrow_returns_up_after_reset(self):
        state = SortState()
        state.apply(1)
        state.apply(1)
        state.reset()
        assert state.arrow() == "▲"


class TestSortColumns:
    def test_has_six_entries(self):
        assert len(SORT_COLUMNS) == 6

    def test_each_entry_is_tuple_of_two_strings(self):
        for entry in SORT_COLUMNS:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            assert all(isinstance(s, str) for s in entry)

    def test_attribute_names_are_valid_connection_fields(self):
        from netmon.monitor.collector import Connection
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(Connection)}
        for attr, _ in SORT_COLUMNS:
            assert attr in field_names, f"'{attr}' not found in Connection fields"

    def test_display_names_are_non_empty(self):
        for _, display_name in SORT_COLUMNS:
            assert display_name.strip() != ""
