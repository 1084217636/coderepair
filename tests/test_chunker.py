from retrieval.chunker import CodeChunker


def test_go_chunker_uses_declaration_boundaries(tmp_path):
    go_file = tmp_path / "service.go"
    go_file.write_text(
        """package sample

import "fmt"

// Service 负责输出问候语
type Service struct {
    Name string
}

// Greet 输出问候信息
func (s *Service) Greet() {
    fmt.Println(s.Name)
}

func helper() string {
    return "ok"
}
""",
        encoding="utf-8",
    )

    chunks = CodeChunker(chunk_size=1000, chunk_overlap=50).chunk_file(go_file, "go")
    chunk_kinds = [chunk.chunk_kind for chunk in chunks]

    assert "file_header" in chunk_kinds
    assert "type" in chunk_kinds
    assert "method" in chunk_kinds
    assert "function" in chunk_kinds

    method_chunk = next(chunk for chunk in chunks if chunk.chunk_kind == "method")
    assert method_chunk.symbol == "Service.Greet"
    assert "func (s *Service) Greet()" in method_chunk.text


def test_go_chunker_splits_large_function_with_overlap(tmp_path):
    repeated_lines = "\n".join(f'    println("line-{index}")' for index in range(20))
    go_file = tmp_path / "large.go"
    go_file.write_text(
        f"""package sample

func huge() {{
{repeated_lines}
}}
""",
        encoding="utf-8",
    )

    chunks = CodeChunker(chunk_size=120, chunk_overlap=30).chunk_file(go_file, "go")
    function_chunks = [chunk for chunk in chunks if chunk.chunk_kind == "function"]

    assert len(function_chunks) >= 2
    assert function_chunks[0].summary.endswith("[part 1]")
    assert function_chunks[1].start_line <= function_chunks[0].end_line
