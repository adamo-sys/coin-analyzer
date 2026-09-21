import json

from capture_import.observation_quality_cli import main


def test_cli_scores_existing_report_without_provider(tmp_path, capsys):
    source = tmp_path / "run.json"
    output = tmp_path / "quality.json"
    source.write_text(
        json.dumps(
            {
                "schema": "coin-analyzer-recognition30-grounded-v1",
                "rows": [
                    {
                        "view_provenance": [
                            {
                                "view": "full_face",
                                "role": "obverse",
                                "visible_text": ["1968"],
                                "date_like": "1968",
                                "denomination_mark": None,
                                "input_tokens": 100,
                                "output_tokens": 10,
                            },
                            {
                                "view": "rim",
                                "role": "obverse",
                                "visible_text": ["HELVETIA"],
                                "date_like": None,
                                "denomination_mark": None,
                                "input_tokens": 90,
                                "output_tokens": 10,
                            },
                        ]
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main([str(source), "--json", str(output)]) == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema"] == "coin-analyzer-observation-quality-v1"
    assert len(report["views"]) == 2
    assert report["pairs"][0]["incremental_comparison_text"] == ["HELVETIA"]
    assert "comparison_incremental_text=1" in capsys.readouterr().out
