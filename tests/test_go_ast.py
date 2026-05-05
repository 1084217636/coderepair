from analyzers.go_ast import GoAnalyzer


def test_go_analyzer_extracts_methods_calls_and_dependency_span(tmp_path):
    (tmp_path / "go.mod").write_text(
        "module github.com/acme/demo\n\ngo 1.21\n",
        encoding="utf-8",
    )
    source = tmp_path / "server.go"
    source.write_text(
        """package main

import (
    "fmt"
    "github.com/acme/demo/internal/service"
    "github.com/sirupsen/logrus"
)

type Server struct{}

func helper() {}

func (s *Server) Start() {
    helper()
    service.Run()
    fmt.Println("ok")
    logrus.Info("started")
}
""",
        encoding="utf-8",
    )

    analysis = GoAnalyzer(tmp_path).analyze_file(source)

    assert analysis["package"] == "main"
    assert "helper" in analysis["functions"]
    assert "Server.Start" in analysis["methods"]
    assert "Server" in analysis["types"]
    assert any(edge["caller"] == "Server.Start" and edge["callee"] == "helper" for edge in analysis["call_edges"])
    assert any(edge["caller"] == "Server.Start" and edge["callee"] == "service.Run" for edge in analysis["call_edges"])
    assert any(edge["caller"] == "Server.Start" and edge["callee"] == "fmt.Println" for edge in analysis["call_edges"])
    assert analysis["dependency_span"]["stdlib_imports"] == 1
    assert analysis["dependency_span"]["local_imports"] == 1
    assert analysis["dependency_span"]["external_imports"] == 1
    assert analysis["dependency_span"]["cross_package_dependencies"] == 2
