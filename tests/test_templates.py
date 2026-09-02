import tomllib

import pytest

from t1_bootstrap import templates
from t1_bootstrap.spec import ProjectSpec


@pytest.fixture
def spec(tmp_path):
    return ProjectSpec(
        name="sales pipeline",
        parent=tmp_path,
        python="3.13",
        directories={"tests", "logs"},
        extras={"ruff", "readme", "git", "cli", "env"},
    )


def test_pyproject_is_valid_toml_with_the_name_filled_in(spec):
    data = tomllib.loads(templates.pyproject(spec))
    assert data["project"]["name"] == "sales-pipeline"
    assert data["project"]["requires-python"] == ">=3.13"
    assert data["project"]["scripts"] == {"sales-pipeline": "sales_pipeline.cli:main"}
    assert data["build-system"]["build-backend"] == "uv_build"


def test_ruff_config_targets_the_chosen_python(spec):
    data = tomllib.loads(templates.pyproject(spec))
    assert data["tool"]["ruff"]["target-version"] == "py313"
    assert data["tool"]["ruff"]["lint"]["isort"]["known-first-party"] == ["sales_pipeline"]


def test_pytest_config_only_appears_with_a_tests_directory(spec):
    assert "pytest" in tomllib.loads(templates.pyproject(spec))["tool"]
    spec.directories.discard("tests")
    assert "pytest" not in tomllib.loads(templates.pyproject(spec))["tool"]


def test_src_layout_needs_no_build_backend_override(spec):
    # uv_build defaults to src/<normalised name>, which is exactly what we generate.
    assert "uv" not in tomllib.loads(templates.pyproject(spec))["tool"]


def test_flat_layout_repoints_the_module_root(spec):
    spec.layout = "flat"
    data = tomllib.loads(templates.pyproject(spec))
    assert data["tool"]["uv"]["build-backend"]["module-root"] == ""
    assert data["tool"]["ruff"]["src"] == ["tests"]


def test_unconventional_module_name_is_stated_explicitly(tmp_path):
    odd = ProjectSpec(name="2fast", parent=tmp_path, python="3.13")
    data = tomllib.loads(templates.pyproject(odd))
    assert data["tool"]["uv"]["build-backend"]["module-name"] == "_2fast"


def test_no_ruff_extra_means_no_ruff_section(spec):
    spec.extras.discard("ruff")
    assert "ruff" not in tomllib.loads(templates.pyproject(spec))["tool"]


def test_generated_modules_are_syntactically_valid(spec):
    for source in (
        templates.package_init(spec),
        templates.cli_module(spec),
        templates.dunder_main(spec),
        templates.logging_module(spec),
        templates.smoke_test(spec),
    ):
        compile(source, "<generated>", "exec")


def test_logging_module_walks_up_to_the_project_root(spec):
    assert "parents[2]" in templates.logging_module(spec)
    spec.layout = "flat"
    assert "parents[1]" in templates.logging_module(spec)


def test_gitignore_includes_directory_specific_rules(spec):
    body = templates.gitignore(spec)
    assert "__pycache__/" in body
    assert "logs/*" in body
    assert "!logs/.gitkeep" in body


def test_readme_carries_the_name_and_quickstart(spec):
    body = templates.readme(spec)
    assert body.startswith("# sales-pipeline")
    assert "uv run pytest" in body
    assert "uv run sales-pipeline" in body


def test_readme_links_to_the_real_repository(spec):
    body = templates.readme(spec)
    assert "https://github.com/tabelle1/t1-bootstrap" in body
    assert "(https://github.com/)" not in body


def test_env_and_its_example_are_different_files(spec):
    env, example = templates.env_file(spec), templates.env_example(spec)
    assert env != example
    assert "Never commit" in env
    assert "SALES_PIPELINE_ENV=local" in env
    assert "SALES_PIPELINE_ENV=local" in example


def test_generated_pyproject_has_no_dangling_per_file_ignores(spec):
    assert "per-file-ignores" not in templates.pyproject(spec)
