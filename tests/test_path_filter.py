from pathlib import Path

from retrieval.filters import PathFilter


def test_path_filter_blocks_platform_source_by_default(tmp_path):
    platform_root = tmp_path
    workspace_root = tmp_path

    core_file = platform_root / "core" / "logger.py"
    app_file = platform_root / "app.py"
    core_file.parent.mkdir(parents=True)
    core_file.write_text("print('logger')\n", encoding="utf-8")
    app_file.write_text("print('app')\n", encoding="utf-8")

    path_filter = PathFilter(platform_root=platform_root, workspace_root=workspace_root)

    assert path_filter.is_valid_path(app_file) is True
    assert path_filter.is_valid_path(core_file) is False


def test_path_filter_allows_platform_source_in_self_dev_mode(tmp_path):
    platform_root = tmp_path
    workspace_root = tmp_path

    core_file = platform_root / "core" / "logger.py"
    llm_file = platform_root / "llm" / "client.py"
    core_file.parent.mkdir(parents=True)
    llm_file.parent.mkdir(parents=True)
    core_file.write_text("print('logger')\n", encoding="utf-8")
    llm_file.write_text("print('client')\n", encoding="utf-8")

    path_filter = PathFilter(
        platform_root=platform_root,
        workspace_root=workspace_root,
        allow_platform_source=True,
    )

    assert path_filter.is_valid_path(core_file) is True
    assert path_filter.is_valid_path(llm_file) is True


def test_path_filter_allows_engineering_files_for_go_workspace(tmp_path):
    platform_root = tmp_path / "platform"
    workspace_root = tmp_path / "workspace"
    platform_root.mkdir()
    workspace_root.mkdir()

    dockerfile = workspace_root / "Dockerfile"
    makefile = workspace_root / "Makefile"
    dockerignore = workspace_root / ".dockerignore"
    gomod = workspace_root / "go.mod"
    readme = workspace_root / "README.md"
    random_txt = workspace_root / "notes.txt"

    for path in [dockerfile, makefile, dockerignore, gomod, readme, random_txt]:
        path.write_text("content\n", encoding="utf-8")

    path_filter = PathFilter(
        platform_root=platform_root,
        workspace_root=workspace_root,
        include_extensions=[".go", ".mod", ".sum", ".md"],
        include_filenames=["Dockerfile", "Makefile", ".dockerignore"],
    )

    assert path_filter.is_valid_path(dockerfile) is True
    assert path_filter.is_valid_path(makefile) is True
    assert path_filter.is_valid_path(dockerignore) is True
    assert path_filter.is_valid_path(gomod) is True
    assert path_filter.is_valid_path(readme) is True
    assert path_filter.is_valid_path(random_txt) is False
