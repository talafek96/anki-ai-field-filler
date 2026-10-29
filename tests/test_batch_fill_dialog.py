"""Tests for the batch fill dialog's screen-fitting layout (issue #17)."""

from __future__ import annotations

from ai_field_filler.ui.batch_fill_dialog import field_grid_position, field_list_height


class TestFieldGridPosition:
    def test_few_fields_stay_in_one_column(self) -> None:
        assert [field_grid_position(i, 8) for i in range(8)] == [(i, 0) for i in range(8)]

    def test_many_fields_split_into_two_columns(self) -> None:
        positions = [field_grid_position(i, 12) for i in range(12)]
        assert positions[:6] == [(i, 0) for i in range(6)]
        assert positions[6:] == [(i, 1) for i in range(6)]

    def test_odd_count_puts_the_extra_field_in_the_first_column(self) -> None:
        positions = [field_grid_position(i, 9) for i in range(9)]
        assert positions[4] == (4, 0)
        assert positions[5] == (0, 1)
        assert max(row for row, _ in positions) == 4

    def test_every_field_gets_a_distinct_cell(self) -> None:
        for count in (1, 9, 12, 40, 41):
            positions = [field_grid_position(i, count) for i in range(count)]
            assert len(set(positions)) == count


class TestFieldListHeight:
    def test_list_shows_in_full_when_it_fits(self) -> None:
        assert field_list_height(content=200, chrome=400, available=1000) == 200

    def test_list_shrinks_to_the_room_left_on_screen(self) -> None:
        # 672 = 1080p at 150% scaling minus the taskbar, as in the issue.
        assert field_list_height(content=900, chrome=400, available=672) == 212

    def test_list_keeps_a_minimum_height_on_tiny_screens(self) -> None:
        assert field_list_height(content=900, chrome=400, available=300) == 120

    def test_short_list_is_never_padded_to_the_minimum(self) -> None:
        assert field_list_height(content=60, chrome=400, available=300) == 60
