import json

from command_registry import CommandContext
from services.prescription_interaction_service import PrescriptionInteractionService


def _write_data(tmp_path):
    payload = {
        "metadata": {"source_url": "test"},
        "drugs": {
            "midazolam": {
                "name": "Midazolam",
                "relationships": [
                    {
                        "enzyme": "3A4/5",
                        "role": "substrate",
                        "strength": "strong",
                        "references": ["https://example.test/reference"],
                    }
                ],
            },
            "clarithromycin": {
                "name": "Clarithromycin",
                "relationships": [
                    {
                        "enzyme": "3A4/5",
                        "role": "inhibitor",
                        "strength": "strong",
                        "references": [],
                    },
                    {
                        "enzyme": "3A4/5",
                        "role": "inhibitor",
                        "strength": None,
                        "references": [],
                    },
                ],
            },
            "rifampin": {
                "name": "Rifampin",
                "relationships": [
                    {
                        "enzyme": "3A4/5",
                        "role": "inducer",
                        "strength": "strong",
                        "references": [],
                    }
                ],
            },
            "st. john's wort": {
                "name": "St. John's Wort",
                "relationships": [
                    {
                        "enzyme": "3A4/5",
                        "role": "inducer",
                        "strength": None,
                        "references": [],
                    }
                ],
            },
        },
    }
    (tmp_path / "prescription_interactions.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_profile_lookup_is_case_insensitive(tmp_path):
    _write_data(tmp_path)
    service = PrescriptionInteractionService(str(tmp_path))
    result = service.format_profile(" MIDAZOLAM ")
    assert "Midazolam" in result
    assert "Substrate: 3A4/5 (strong)" in result


def test_pair_analysis_reports_inhibitor_and_inducer_directions(tmp_path):
    _write_data(tmp_path)
    service = PrescriptionInteractionService(str(tmp_path))
    result = service.check_interactions(["midazolam", "clarithromycin", "rifampin"])
    assert (
        "Clarithromycin inhibitor of 3A4/5 may increase exposure to Midazolam" in result
    )
    assert result.count("may increase exposure to Midazolam") == 1
    assert "Rifampin inducer of 3A4/5 may reduce exposure to Midazolam" in result
    assert (
        "Clarithromycin inhibitor of 3A4/5 may increase exposure to Rifampin"
        not in result
    )


def test_duplicate_and_unknown_names_are_handled(tmp_path):
    _write_data(tmp_path)
    service = PrescriptionInteractionService(str(tmp_path))
    result = service.check_interactions(["midazolam", "Midazolam", "missing"])
    assert result.count("Unknown prescription drugs") == 1
    assert "missing" in result


def test_invalid_database_falls_back_to_empty(tmp_path):
    (tmp_path / "prescription_interactions.json").write_text("{", encoding="utf-8")
    service = PrescriptionInteractionService(str(tmp_path))
    assert service.drugs == {}


def test_rxdrugs_command_preserves_multi_word_names():
    from cmd_modules.services import rxdrugs_command

    context = CommandContext(
        command="rxdrugs",
        args=[],
        raw_message="!rxdrugs midazolam, St. John's Wort",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    context.args_text = "midazolam, St. John's Wort"
    calls = []
    result = rxdrugs_command(context, {"check_prescription_interactions": calls.append})
    assert result is None
    assert calls == ["midazolam, St. John's Wort"]


def test_rxdrugs_command_usage():
    from cmd_modules.services import rxdrugs_command

    context = CommandContext(
        command="rxdrugs",
        args=[],
        raw_message="!rxdrugs",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    context.args_text = ""
    assert "Usage: !rxdrugs" in rxdrugs_command(context, {})
