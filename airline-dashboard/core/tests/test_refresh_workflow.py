"""Exercise the refresh workflow's real Bash argument construction offline."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "refresh-data.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
STEPS = {step["name"]: step for step in WORKFLOW["jobs"]["build-data"]["steps"] if "name" in step}


@pytest.fixture
def bash():
    if os.name == "nt":
        git = shutil.which("git")
        executable = Path(git).parents[1] / "bin" / "bash.exe" if git else None
    else:
        executable = shutil.which("bash")
    if not executable or not Path(executable).exists():
        pytest.skip("Bash is required to exercise GitHub Actions shell steps")
    return str(executable)


def run_step(bash, tmp_path, name, env, prefix=""):
    return subprocess.run(
        [bash, "-e", "-o", "pipefail", "-c", prefix + STEPS[name]["run"]],
        cwd=tmp_path,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )


def parameters(bash, tmp_path, **inputs):
    env = {
        "EVENT_NAME": "workflow_dispatch",
        "GITHUB_OUTPUT": "outputs",
        "INPUT_AIRLINES": "AAL DAL",
        "INPUT_YEARS": "2024 2025",
        "INPUT_PERIODS": "Q2 FY",
        **inputs,
    }
    result = run_step(bash, tmp_path, "Determine run parameters", env)
    return result


@pytest.mark.parametrize(
    "source,parser,expected",
    [
        ("both", "true", ["auto", "manual"]),
        ("auto", "true", ["auto"]),
        ("manual", "false", ["manual"]),
    ],
)
def test_sources_flags_and_insights_inputs(bash, tmp_path, source, parser, expected):
    result = parameters(
        bash,
        tmp_path,
        INPUT_SOURCES=source,
        INPUT_FILING_PARSER="true",
        INPUT_OVERWRITE="true",
        INPUT_SHARE_DATA="true",
        INPUT_INSIGHTS="false",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    outputs = dict(line.split("=", 1) for line in (tmp_path / "outputs").read_text().splitlines())
    assert outputs["filing_parser"] == parser
    assert outputs["insights"] == "false"
    result = run_step(
        bash,
        tmp_path,
        "Build financials and optional buybacks",
        {key.upper(): value for key, value in outputs.items()},
        prefix='python() { printf "%s\\n" "$@" > arguments; }\n',
    )
    assert result.returncode == 0, result.stdout + result.stderr
    args = (tmp_path / "arguments").read_text().splitlines()
    assert args[:12] == [
        "-m",
        "scripts.build_data",
        "--airlines",
        "AAL",
        "DAL",
        "--years",
        "2024",
        "2025",
        "--periods",
        "Q2",
        "FY",
        "--sources",
    ]
    assert args[12 : 12 + len(expected)] == expected
    assert "--overwrite" in args
    assert "--share-data" in args
    assert ("--use-filing-parser" in args) == (parser == "true")
    assert STEPS["Generate insights"]["if"] == "steps.params.outputs.insights == 'true'"


def test_workflow_dispatch_defaults_and_schedule_compatibility(bash, tmp_path):
    # BaseLoader avoids YAML 1.1 interpreting GitHub's "on" key as a boolean.
    inputs = yaml.load(WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)["on"][
        "workflow_dispatch"
    ]["inputs"]
    assert inputs["use_filing_parser"]["default"] == "true"
    assert inputs["sources"]["default"] == "both"
    result = parameters(bash, tmp_path, EVENT_NAME="schedule")
    assert result.returncode == 0, result.stdout + result.stderr
    outputs = dict(line.split("=", 1) for line in (tmp_path / "outputs").read_text().splitlines())
    assert outputs["sources"] == "auto manual"
    assert outputs["filing_parser"] == "true"
    assert outputs["overwrite"] == "false"
    assert outputs["share_data"] == "false"
    assert outputs["insights"] == "true"


@pytest.mark.parametrize(
    "inputs",
    [
        {"INPUT_AIRLINES": "AAL; touch injected"},
        {"INPUT_YEARS": "$(touch injected)"},
        {"INPUT_PERIODS": "Q2\nsources=manual"},
        {"INPUT_PERIODS": "Q5"},
        {"INPUT_AIRLINES": "   "},
        {"INPUT_SOURCES": "invalid"},
        {"INPUT_OVERWRITE": "invalid"},
    ],
)
def test_invalid_inputs_fail_before_building(bash, tmp_path, inputs):
    result = parameters(bash, tmp_path, **inputs)
    assert result.returncode != 0
    assert "::error::" in result.stdout
    assert not (tmp_path / "outputs").exists()
    assert not (tmp_path / "injected").exists()


def test_insight_arguments_are_passed_as_lists(bash, tmp_path):
    result = run_step(
        bash,
        tmp_path,
        "Generate insights",
        {"AIRLINES": "AAL DAL", "YEARS": "2024 2025", "PERIODS": "Q2 FY"},
        prefix='python() { printf "%s\\n" "$@" > arguments; }\n',
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "arguments").read_text().splitlines() == [
        "-m",
        "sec_pipeline.pipeline",
        "--airlines",
        "AAL",
        "DAL",
        "--years",
        "2024",
        "2025",
        "--periods",
        "Q2",
        "FY",
    ]
