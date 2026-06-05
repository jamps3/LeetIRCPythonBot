import json
from unittest.mock import Mock, patch

from services.danger_announcement_service import (
    DangerAnnouncementService,
    format_danger_announcement,
    parse_danger_announcements_html,
)

SAMPLE_HTML = """
<div class="col-sm-10 col-md-10 col-lg-11">
  <h2 class="title">Vaaratiedote</h2>
  <span class="date">Pe 5.6.2026 11:42</span>
  <p>Tämä on vaaratiedotteiden välitysjärjestelmän kokeilu. Kokeilu ei edellytä väestöltä toimenpiteitä.</p>
  <p>Dát lea váralašvuođadieđáhusaid almmustahttinortnega geahččaleapmi.</p>
  <p>Taat lii vaarâtiäđáttâsâi almostittemvuáháduv iskâm.</p>
  <p>Tät lij vaarrteâđtõõzzi vuõltteemsystee´m ǩiõččlõddmõš.</p>
</div>
"""


def test_parse_danger_announcements_uses_only_finnish_paragraph():
    announcements = parse_danger_announcements_html(SAMPLE_HTML)

    assert announcements == [
        {
            "title": "Vaaratiedote",
            "date": "Pe 5.6.2026 11:42",
            "text": "Tämä on vaaratiedotteiden välitysjärjestelmän kokeilu. Kokeilu ei edellytä väestöltä toimenpiteitä.",
        }
    ]
    assert "Dát lea" not in announcements[0]["text"]
    assert "Taat lii" not in announcements[0]["text"]
    assert "Tät lij" not in announcements[0]["text"]


def test_format_danger_announcement():
    message = format_danger_announcement(
        {
            "title": "Vaaratiedote",
            "date": "Pe 5.6.2026 11:42",
            "text": "Suomenkielinen teksti.",
        }
    )

    assert message == "⚠ Vaaratiedote Pe 5.6.2026 11:42: Suomenkielinen teksti."


def test_check_new_announcements_deduplicates_and_saves(tmp_path):
    state_file = tmp_path / "state.json"
    service = DangerAnnouncementService(
        callback=Mock(),
        state_file=str(state_file),
    )

    with patch(
        "services.danger_announcement_service.fetch_danger_announcements",
        return_value=[
            {
                "title": "Vaaratiedote",
                "date": "Pe 5.6.2026 11:42",
                "text": "Suomenkielinen teksti.",
            }
        ],
    ):
        first_messages = service.check_new_announcements()
        second_messages = service.check_new_announcements()

    assert first_messages == [
        "⚠ Vaaratiedote Pe 5.6.2026 11:42: Suomenkielinen teksti."
    ]
    assert second_messages == []

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["danger_announcements"]["seen_hashes"]) == 1


def test_monitor_loop_calls_callback_for_new_announcements(tmp_path):
    callback = Mock()
    service = DangerAnnouncementService(
        callback=callback,
        state_file=str(tmp_path / "state.json"),
        check_interval=1,
    )

    def fake_check():
        service.running = False
        return ["⚠ Vaaratiedote: test"]

    service.check_new_announcements = Mock(side_effect=fake_check)
    service.running = True
    service._monitor_loop()

    callback.assert_called_once_with(["⚠ Vaaratiedote: test"])
