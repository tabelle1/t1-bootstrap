import pytest

from t1_bootstrap.spec import ProjectSpec, modulize, slugify


@pytest.mark.parametrize(
    ("raw", "slug", "module"),
    [
        ("sales pipeline", "sales-pipeline", "sales_pipeline"),
        ("  My Cool Project  ", "my-cool-project", "my_cool_project"),
        ("ETL_2024", "etl-2024", "etl_2024"),
        ("a---b", "a-b", "a_b"),
        ("2fast", "2fast", "_2fast"),
    ],
)
def test_name_normalisation(raw: str, slug: str, module: str) -> None:
    assert slugify(raw) == slug
    assert modulize(raw) == module


def test_blank_name_is_the_only_problem_reported(tmp_path):
    spec = ProjectSpec(name="   ", parent=tmp_path)
    assert spec.problems() == ["Give the project a name."]


def test_python_keyword_is_rejected(tmp_path):
    spec = ProjectSpec(name="class", parent=tmp_path)
    assert any("not a usable Python package name" in p for p in spec.problems())


def test_name_without_letters_is_rejected(tmp_path):
    assert any(
        "no letters or digits" in p for p in ProjectSpec(name="---", parent=tmp_path).problems()
    )


def test_missing_parent_is_reported(tmp_path):
    spec = ProjectSpec(name="demo", parent=tmp_path / "nope")
    assert any("does not exist" in p for p in spec.problems())


def test_existing_empty_directory_is_fine(tmp_path):
    (tmp_path / "demo").mkdir()
    assert ProjectSpec(name="demo", parent=tmp_path).is_valid


def test_existing_non_empty_directory_is_not(tmp_path):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "keep.txt").write_text("x")
    spec = ProjectSpec(name="demo", parent=tmp_path)
    assert any("not empty" in p for p in spec.problems())


def test_layout_drives_the_package_directory(tmp_path):
    src = ProjectSpec(name="demo", parent=tmp_path, layout="src")
    flat = ProjectSpec(name="demo", parent=tmp_path, layout="flat")
    assert src.package_dir == "src/demo"
    assert flat.package_dir == "demo"


def test_extras_pull_in_the_directories_they_need(tmp_path):
    spec = ProjectSpec(name="demo", parent=tmp_path, extras={"logging"})
    spec.resolve_implications()
    assert "logs" in spec.directories


def test_planned_files_track_the_extras(tmp_path):
    bare = ProjectSpec(name="demo", parent=tmp_path)
    assert ".gitignore" not in bare.planned_files()

    loaded = ProjectSpec(name="demo", parent=tmp_path, extras={"git", "cli", "env"})
    files = loaded.planned_files()
    assert ".gitignore" in files
    assert ".env.example" in files
    assert "src/demo/cli.py" in files


def test_tree_lists_directories_before_files(tmp_path):
    spec = ProjectSpec(name="demo", parent=tmp_path, directories={"data"}, extras={"readme"})
    kinds = [kind for _, _, kind in spec.tree()]
    assert kinds.index("dir") < kinds.index("file")


def test_gitignore_extras_come_from_selected_directories(tmp_path):
    spec = ProjectSpec(name="demo", parent=tmp_path, directories={"logs"})
    assert "logs/*" in spec.gitignore_extras()
    assert ProjectSpec(name="demo", parent=tmp_path).gitignore_extras() == []
