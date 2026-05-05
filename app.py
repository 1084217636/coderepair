"""
CodeRepair - 代码分析与自动修复研发辅助平台

CLI 主入口
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

try:
    import click
except ImportError:
    print("Error: click 模块未安装。请运行: python3 -m pip install click")
    sys.exit(1)

from core.logger import get_logger
from core.multi_agent import MultiAgentCoordinator
from core.planner import TaskPlanner, Language
from core.session import SessionManager, SessionContext
from core.pipeline import Pipeline, PipelineContext
from core.tool_calling import ToolLedger
from retrieval.filters import PathFilter
from retrieval.scanner import RepositoryScanner
from retrieval.chunker import CodeChunker
from retrieval.retriever import Retriever
from evaluation import RunMetricsEvaluator
from analyzers.language_detector import LanguageDetector
from analyzers.go_ast import GoAnalyzer
from llm.client import LLMClient
from llm.prompt_builder import PromptBuilder
from executors.validator import ValidationResult, Validator
from outputs.artifact_manager import ArtifactManager
from outputs.diff_formatter import DiffFormatter
from outputs.formatters import ResultFormatter
from outputs.quality_summary import QualitySummaryBuilder
from outputs.task_report import TaskReportBuilder
from patcher import FileWriter
from sandbox import DockerRunner
from validators.go_checker import GoChecker
from config import settings

logger = get_logger(__name__)


class CodeRepairPlatform:
    """
    代码修复平台主类
    """
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_review_rounds: int = 1,
    ):
        self.planner = TaskPlanner()
        self.session_manager = SessionManager(settings.ARTIFACTS_ROOT)
        self.artifact_manager = ArtifactManager(settings.ARTIFACTS_ROOT)
        self.provider_override = provider
        self.model_override = model
        self.temperature_override = temperature
        self.max_review_rounds = max_review_rounds
        self.logger = get_logger(__name__)

    def _create_llm_client(self) -> LLMClient:
        """按当前覆盖配置创建 LLM 客户端"""
        return LLMClient(
            provider=self.provider_override,
            model=self.model_override,
            temperature=self.temperature_override,
        )

    def _normalize_apply_path(self, workspace_path: Path, apply_file: str) -> str:
        """将 apply_file 规范化为相对 workspace 的路径"""
        workspace_path = workspace_path.resolve()
        apply_path = Path(apply_file)
        candidate = apply_path if apply_path.is_absolute() else workspace_path / apply_path
        resolved = candidate.resolve(strict=False)

        try:
            return str(resolved.relative_to(workspace_path))
        except ValueError as e:
            raise ValueError(f"--apply-file 必须位于 workspace 内: {apply_file}") from e

    def _apply_generated_code(
        self,
        workspace_path: Path,
        apply_file: str,
        target_language: str,
        extracted_code_blocks: list[str],
        llm_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        在条件明确时将提取出的第一个代码块写回目标文件。

        这是一个保守的“最小闭环”能力：
        - 仅在用户显式传入 --apply-file 时启用
        - 默认拒绝将 mock 回复写回文件
        - 对 Go 代码要求看起来像完整文件（至少包含 package）
        """
        apply_file = self._normalize_apply_path(workspace_path, apply_file)

        if llm_response.get("stop_reason") == "mock":
            self.logger.warning("[Apply] 当前为 mock 回复，跳过自动写回")
            return {
                "status": "skipped",
                "reason": "mock_response",
                "file": apply_file,
            }

        if not extracted_code_blocks:
            self.logger.warning("[Apply] 未提取到代码块，跳过自动写回")
            return {
                "status": "skipped",
                "reason": "no_code_block",
                "file": apply_file,
            }

        new_content = extracted_code_blocks[0].strip()
        if target_language == "go" and "package " not in new_content:
            self.logger.warning("[Apply] 提取到的 Go 代码不像完整文件，跳过自动写回")
            return {
                "status": "skipped",
                "reason": "not_full_file",
                "file": apply_file,
            }

        full_path = workspace_path / apply_file
        old_content = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
        if old_content == new_content:
            self.logger.info("[Apply] 新旧内容一致，无需写回")
            return {
                "status": "skipped",
                "reason": "no_change",
                "file": apply_file,
            }

        writer = FileWriter(str(workspace_path))
        write_result = writer.write_file(apply_file, new_content)
        if isinstance(write_result.get("backup"), Path):
            write_result["backup"] = str(write_result["backup"])

        formatter = DiffFormatter(str(workspace_path))
        diff_result = formatter.generate_diff(
            file_path=apply_file,
            old_content=old_content,
            new_content=new_content,
        )
        self.artifact_manager.save_json_artifact("08_applied_diff.json", diff_result)
        self.artifact_manager.save_artifact(
            "08_applied_diff.md",
            formatter.format_diff_for_markdown(diff_result["diff"]),
        )

        return {
            "status": "applied",
            "file": apply_file,
            "write_result": write_result,
            "diff_stats": diff_result["stats"],
        }

    def _resolve_validation_target(
        self,
        language: str,
        validate_cmd: Optional[str],
    ) -> tuple[str, Optional[str]]:
        """根据语言和用户输入决定验证阶段和命令。"""
        if validate_cmd:
            return "custom", validate_cmd
        if language == "go":
            return "build", None
        if language == "python":
            return "test", None
        return "custom", None

    def _run_local_validation(
        self,
        workspace_path: Path,
        language: str,
        validate_cmd: Optional[str],
    ) -> Dict[str, Any]:
        """执行本地验证。"""
        validator = Validator(workspace_path)
        if validate_cmd:
            return validator.run_custom(validate_cmd).to_dict()
        if language == "go":
            return validator.run_go_build().to_dict()
        if language == "python":
            return validator.run_python_tests().to_dict()
        return ValidationResult.skipped("custom", f"language_not_supported:{language}").to_dict()

    def _run_docker_validation(
        self,
        workspace_path: Path,
        language: str,
        stage: str,
        validate_cmd: Optional[str],
    ) -> Dict[str, Any]:
        """执行 Docker 验证；不可用时返回 skipped。"""
        runner, error = DockerRunner.try_create()
        if runner is None:
            return ValidationResult.skipped(stage, f"docker_unavailable:{error}").to_dict()

        if language != "go":
            return ValidationResult.skipped(stage, f"docker_not_supported_for_language:{language}").to_dict()

        if validate_cmd:
            sandbox_result = runner.run_custom(
                str(workspace_path),
                [f"cd /workspace && {validate_cmd}"],
            )
        elif stage == "test":
            sandbox_result = runner.run_tests(str(workspace_path))
        else:
            sandbox_result = runner.run_compilation(str(workspace_path))

        return ValidationResult.from_sandbox_result(sandbox_result, stage=stage).to_dict()

    def _run_validation(
        self,
        workspace_path: Path,
        language: str,
        validation_mode: str,
        validate_cmd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """统一本地 / Docker / 自动降级验证入口。"""
        stage, resolved_cmd = self._resolve_validation_target(language, validate_cmd)

        if validation_mode == "docker":
            validation_result = self._run_docker_validation(
                workspace_path,
                language,
                stage=stage,
                validate_cmd=resolved_cmd,
            )
            if validation_result.get("skipped_reason"):
                self.logger.warning(
                    f"[Stage 9] Docker 验证不可用，当前结果未验证 | reason={validation_result['skipped_reason']}"
                )
            return validation_result

        if validation_mode == "auto" and language == "go":
            docker_result = self._run_docker_validation(
                workspace_path,
                language,
                stage=stage,
                validate_cmd=resolved_cmd,
            )
            if docker_result.get("source") != "skipped":
                return docker_result

            self.logger.warning(
                f"[Stage 9] Docker 不可用，自动降级到本地验证 | reason={docker_result.get('skipped_reason')}"
            )
            local_result = self._run_local_validation(workspace_path, language, resolved_cmd)
            local_result["fallback_reason"] = docker_result.get("skipped_reason")
            return local_result

        return self._run_local_validation(workspace_path, language, resolved_cmd)

    def _load_current_patch_diff(self) -> str:
        """读取当前 session 的 unified diff，缺失时返回空串。"""
        try:
            diff_path = self.artifact_manager.get_session_dir() / "08_applied_diff.json"
        except RuntimeError:
            return ""

        if not diff_path.exists():
            return ""

        try:
            payload = json.loads(diff_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""
        return payload.get("diff", "")

    def _save_delivery_artifacts(
        self,
        *,
        result: Dict[str, Any],
        analysis_output: Dict[str, Any],
        retrieval_summary: Dict[str, Any],
        tool_ledger: ToolLedger,
    ) -> None:
        """保存面向交付和复盘的标准产物。"""
        builder = TaskReportBuilder()
        patch_diff = self._load_current_patch_diff()
        artifact_names = [
            "task_report.md",
            "patch.diff",
            "validate.log",
            "review.json",
            "summary.json",
            "tool_calls.json",
            "runner.log",
        ]

        self.artifact_manager.save_artifact(
            "patch.diff",
            patch_diff if patch_diff else "No patch generated.\n",
        )
        self.artifact_manager.save_artifact(
            "validate.log",
            builder.render_validation_log(result.get("validation_output")),
        )
        self.artifact_manager.save_json_artifact(
            "review.json",
            builder.build_review_payload(result),
        )

        tool_ledger.record(
            "report",
            {"session_id": result.get("session_id")},
            {"artifacts": artifact_names},
        )
        tool_calls = tool_ledger.to_dict()
        self.artifact_manager.save_json_artifact(
            "summary.json",
            QualitySummaryBuilder.build(result, tool_calls),
        )
        self.artifact_manager.save_json_artifact("tool_calls.json", tool_calls)
        self.artifact_manager.save_artifact(
            "task_report.md",
            builder.render_task_report(
                result=result,
                analysis_output=analysis_output,
                retrieval_summary=retrieval_summary,
                tool_calls=tool_calls,
                artifact_names=artifact_names,
            ),
        )

    def _apply_with_lifecycle(
        self,
        workspace_path: Path,
        apply_file: str,
        language: str,
        extracted_code_blocks: list[str],
        llm_response: Dict[str, Any],
        validate: bool,
        validation_mode: str,
        validate_cmd: Optional[str],
        rollback_on_failure: bool,
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """将写回、验证和按需回滚串成一个保守闭环。"""
        target_language = CodeChunker.detect_language(Path(apply_file), language)
        apply_result = self._apply_generated_code(
            workspace_path=workspace_path,
            apply_file=apply_file,
            target_language=target_language,
            extracted_code_blocks=extracted_code_blocks,
            llm_response=llm_response,
        )

        if apply_result.get("status") != "applied" or not validate:
            return apply_result, None

        validation_result = self._run_validation(
            workspace_path=workspace_path,
            language=language,
            validation_mode=validation_mode,
            validate_cmd=validate_cmd,
        )
        apply_result["validation_output"] = validation_result

        if validation_result.get("success"):
            apply_result["status"] = "validated"
            return apply_result, validation_result

        if validation_result.get("skipped_reason"):
            apply_result["status"] = "applied_unverified"
            return apply_result, validation_result

        apply_result["status"] = "validate_failed"
        if validation_result.get("timed_out"):
            apply_result["rollback_output"] = {
                "status": "skipped",
                "file": apply_result.get("file"),
                "reason": "validation_timeout",
            }
            return apply_result, validation_result

        if not rollback_on_failure:
            apply_result["rollback_output"] = {
                "status": "skipped",
                "file": apply_result.get("file"),
                "reason": "rollback_disabled",
            }
            return apply_result, validation_result

        backup_path = (apply_result.get("write_result") or {}).get("backup")
        if not backup_path:
            apply_result["rollback_output"] = {
                "status": "warning",
                "file": apply_result.get("file"),
                "reason": "backup_not_available",
            }
            return apply_result, validation_result

        writer = FileWriter(str(workspace_path))
        rollback_output = writer.restore_backup(apply_result["file"], backup_path)
        apply_result["rollback_output"] = rollback_output
        apply_result["status"] = (
            "rolled_back" if rollback_output.get("status") == "success" else "rollback_failed"
        )
        return apply_result, validation_result

    def _filter_scan_result(
        self,
        scan_result: Dict[str, Any],
        workspace_path: Path,
        focus_file: str,
    ) -> Dict[str, Any]:
        """将扫描结果收敛到指定文件或目录，便于局部分析和自举开发。"""
        focus_path = Path(focus_file)
        if focus_path.is_absolute():
            try:
                focus_path = focus_path.relative_to(workspace_path)
            except ValueError as e:
                raise ValueError(f"--focus-file 必须位于 workspace 内: {focus_file}") from e

        target = (workspace_path / focus_path).resolve()
        if not target.exists():
            raise ValueError(f"--focus-file 不存在: {focus_file}")

        def matches(path: Path) -> bool:
            resolved = path.resolve()
            if target.is_dir():
                try:
                    resolved.relative_to(target)
                    return True
                except ValueError:
                    return False
            return resolved == target

        filtered_files = [path for path in scan_result["files"] if matches(path)]
        if not filtered_files:
            raise ValueError(f"--focus-file 未匹配到任何可分析文件: {focus_file}")

        filtered_go_files = [path for path in scan_result.get("go_files_list", []) if matches(path)]
        filtered_py_files = [path for path in scan_result.get("py_files_list", []) if matches(path)]
        filtered_engineering_files = [path for path in scan_result.get("engineering_files_list", []) if matches(path)]

        self.logger.info(
            f"[Stage 3] 按 focus_file 收敛扫描范围 | "
            f"focus_file={focus_file} | matched_files={len(filtered_files)}"
        )

        return {
            **scan_result,
            "focus_file": str(focus_path),
            "total_files": len(filtered_files),
            "go_files": len(filtered_go_files),
            "py_files": len(filtered_py_files),
            "engineering_files": len(filtered_engineering_files),
            "files": filtered_files,
            "go_files_list": filtered_go_files,
            "py_files_list": filtered_py_files,
            "engineering_files_list": filtered_engineering_files,
        }
    
    def run(
        self,
        user_input: str,
        workspace_root: str,
        session_id: str = None,
        validate: bool = True,
        apply_file: Optional[str] = None,
        self_dev: bool = False,
        focus_file: Optional[str] = None,
        mode: str = "single",
        validation_mode: str = "auto",
        validate_cmd: Optional[str] = None,
        rollback_on_failure: bool = True,
        artifacts_keep: Optional[int] = None,
        artifacts_retention_days: Optional[int] = None,
    ) -> Dict:
        """
        执行完整的修复流程
        
        Args:
            user_input: 用户输入的需求/问题
            workspace_root: 目标项目根目录
            session_id: 可选的上一轮 session_id（用于 follow-up）
            validate: 是否执行验证步骤
            apply_file: 可选。将提取出的第一个完整代码块写回到该相对文件路径
            self_dev: 是否允许扫描平台自身源码，用于自举开发
            focus_file: 可选。仅聚焦某个文件或目录，减少上下文和超时风险
            mode: 执行模式（single / multi）
            validation_mode: 验证模式（auto / local / docker）
            validate_cmd: 自定义验证命令
            rollback_on_failure: 验证失败时是否自动从备份回滚
            artifacts_keep: 最多保留多少个最近 session
            artifacts_retention_days: 最多保留多少天的 session
        
        Returns:
            执行结果字典
        """
        from datetime import datetime

        previous_session_id = session_id
        current_session_id = self.session_manager.create_session_id()

        # 创建 artifacts 目录
        keep_last = (
            artifacts_keep
            if artifacts_keep is not None
            else (settings.ARTIFACT_RETENTION_SESSIONS if settings.ARTIFACT_AUTO_CLEANUP else None)
        )
        retention_days = (
            artifacts_retention_days
            if artifacts_retention_days is not None
            else (settings.ARTIFACT_RETENTION_DAYS if settings.ARTIFACT_AUTO_CLEANUP else None)
        )
        session_dir = self.artifact_manager.create_session(
            current_session_id,
            keep_last=keep_last,
            retention_days=retention_days,
        )
        
        # 保存输入
        self.artifact_manager.save_artifact("01_input.txt", user_input)
        
        # ========== Stage 1: 任务规划 ==========
        workspace_path = Path(workspace_root)
        if not workspace_path.exists():
            self.logger.error(f"工作目录不存在: {workspace_root}")
            raise ValueError(f"Workspace not found: {workspace_root}")
        tool_ledger = ToolLedger(workspace_path)
        self.artifact_manager.save_json_artifact(
            "00_tool_schema.json",
            tool_ledger.to_schema_document(),
        )
        
        task_plan = self.planner.plan(user_input, workspace_root, previous_session_id)

        analysis_output = {
            "task_type": task_plan.task_type.value,
            "language": task_plan.language.value,
            "workspace_root": str(workspace_path.resolve()),
            "user_query": user_input,
            "self_dev": self_dev,
            "mode": mode,
            "validation_mode": validation_mode,
        }
        if validate_cmd:
            analysis_output["validate_cmd"] = validate_cmd
        if focus_file:
            analysis_output["focus_file"] = focus_file
        if previous_session_id:
            analysis_output["parent_session_id"] = previous_session_id

        previous_context = None
        if previous_session_id:
            previous_context = self.session_manager.load_session(previous_session_id)
            if previous_context:
                self.session_manager.add_feedback(previous_session_id, user_input)
            else:
                self.logger.warning(
                    f"[Session] 未找到上一轮会话，将继续执行但不会注入历史上下文 | session_id={previous_session_id}"
                )

        # ========== Stage 2-3: 扫描与过滤 ==========
        self.logger.info(f"[Stage 2] 设置检索范围")
        self.logger.info(f"  - 平台根目录: {settings.PLATFORM_ROOT}")
        self.logger.info(f"  - 项目根目录: {workspace_root}")
        self.logger.info(f"  - 排除规则已激活（防止平台代码污染）")
        
        path_filter = PathFilter(
            platform_root=settings.PLATFORM_ROOT,
            workspace_root=workspace_path,
            exclude_patterns=settings.EXCLUDE_PATTERNS,
            include_extensions=settings.INCLUDE_EXTENSIONS.get(task_plan.language.value, [".go"]),
            include_filenames=settings.INCLUDE_FILENAMES.get(task_plan.language.value, []),
            allow_platform_source=self_dev,
        )
        
        # ========== Stage 3: 仓库扫描 ==========
        scanner = RepositoryScanner(path_filter)
        scan_result = scanner.scan()
        if focus_file:
            scan_result = self._filter_scan_result(scan_result, workspace_path, focus_file)
        analysis_output.update(
            {
                "scanned_files": scan_result.get("total_files", 0),
                "go_files": scan_result.get("go_files", 0),
                "python_files": scan_result.get("py_files", 0),
                "engineering_files": scan_result.get("engineering_files", 0),
            }
        )
        tool_ledger.record(
            "repository_scan",
            {
                "workspace_root": str(workspace_path.resolve()),
                "focus_file": focus_file,
                "self_dev": self_dev,
            },
            {
                "total_files": scan_result.get("total_files", 0),
                "go_files": scan_result.get("go_files", 0),
                "python_files": scan_result.get("py_files", 0),
                "engineering_files": scan_result.get("engineering_files", 0),
            },
        )
        
        # ========== Stage 4: 代码结构分析 ==========
        self.logger.info(f"[Stage 4] 代码结构分析")

        if task_plan.language == Language.GO:
            analyzer = GoAnalyzer(workspace_path)
            go_analysis_results = []
            for file_path in scan_result.get("go_files_list", [])[: settings.ANALYSIS_MAX_FILES]:
                file_analysis = analyzer.analyze_file(file_path)
                if file_analysis:
                    go_analysis_results.append(file_analysis)

            if go_analysis_results:
                all_imports = sorted({
                    item
                    for analysis in go_analysis_results
                    for item in analysis.get("imports", [])
                })
                all_functions = sorted({
                    item
                    for analysis in go_analysis_results
                    for item in analysis.get("functions", [])
                })
                all_methods = sorted({
                    item
                    for analysis in go_analysis_results
                    for item in analysis.get("methods", [])
                })
                all_types = sorted({
                    item
                    for analysis in go_analysis_results
                    for item in analysis.get("types", [])
                })
                call_edges = []
                seen_edges = set()
                dependency_summary = {
                    "stdlib_imports": 0,
                    "local_imports": 0,
                    "external_imports": 0,
                    "max_import_depth": 0,
                    "cross_package_dependencies": 0,
                }
                for analysis in go_analysis_results:
                    for edge in analysis.get("call_edges", []):
                        key = (edge["caller"], edge["callee"], edge["line"])
                        if key not in seen_edges:
                            seen_edges.add(key)
                            call_edges.append(edge)
                    dep = analysis.get("dependency_span", {})
                    dependency_summary["stdlib_imports"] += dep.get("stdlib_imports", 0)
                    dependency_summary["local_imports"] += dep.get("local_imports", 0)
                    dependency_summary["external_imports"] += dep.get("external_imports", 0)
                    dependency_summary["cross_package_dependencies"] += dep.get("cross_package_dependencies", 0)
                    dependency_summary["max_import_depth"] = max(
                        dependency_summary["max_import_depth"],
                        dep.get("max_import_depth", 0),
                    )

                analysis_output.update({
                    "package": go_analysis_results[0].get("package"),
                    "imports": all_imports,
                    "functions": all_functions,
                    "methods": all_methods,
                    "types": all_types,
                    "call_relations_count": len(call_edges),
                    "dependency_span": dependency_summary,
                    "analyzed_files": len(go_analysis_results),
                })
                self.artifact_manager.save_json_artifact(
                    "02_call_graph.json",
                    {
                        "call_relations": call_edges,
                        "dependency_span": dependency_summary,
                    },
                )

                self.logger.info(
                    f"[Stage 4] Go 分析完成 | files={len(go_analysis_results)} | "
                    f"functions={len(all_functions)} | methods={len(all_methods)} | "
                    f"types={len(all_types)} | call_edges={len(call_edges)}"
                )

            go_checker = GoChecker(str(workspace_path))
            go_precheck = go_checker.check_all()
            precheck_summary = {
                key: value.get("total_issues", 0)
                for key, value in go_precheck.items()
                if isinstance(value, dict)
            }
            analysis_output["go_precheck_summary"] = precheck_summary
            self.artifact_manager.save_json_artifact("02_go_precheck.json", go_precheck)

        tool_ledger.record(
            "go_ast_analyze",
            {"language": task_plan.language.value},
            {
                "analyzed_files": analysis_output.get("analyzed_files", 0),
                "functions": len(analysis_output.get("functions", [])),
                "methods": len(analysis_output.get("methods", [])),
                "types": len(analysis_output.get("types", [])),
                "call_relations_count": analysis_output.get("call_relations_count", 0),
            },
            status="success" if task_plan.language == Language.GO else "skipped",
        )

        chunker = CodeChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        
        all_chunks = []
        for file_path in scan_result["files"][: settings.RETRIEVAL_MAX_FILES]:
            chunks = chunker.chunk_file(file_path, task_plan.language.value)
            all_chunks.extend([c.to_dict() for c in chunks])
        
        self.logger.info(f"[Stage 4] 分块完成 | 总 chunks 数={len(all_chunks)}")
        self.artifact_manager.save_json_artifact("02_analysis.json", analysis_output)
        
        # ========== Stage 5: 检索 ==========
        retriever = Retriever(
            all_chunks,
            top_k=settings.RETRIEVAL_TOP_K,
            workspace_root=workspace_path,
            backend=settings.RAG_BACKEND,
            vector_db_path=settings.VECTOR_DB_PATH,
            lexical_backend=settings.LEXICAL_BACKEND,
            bm25_k1=settings.BM25_K1,
            bm25_b=settings.BM25_B,
            embedding_provider=settings.EMBEDDING_PROVIDER,
            embedding_dim=settings.VECTOR_EMBEDDING_DIM,
            vector_candidates=settings.VECTOR_RETRIEVAL_CANDIDATES,
            rerank_enabled=settings.RERANK_ENABLED,
            rerank_top_n=settings.RERANK_TOP_N,
            ollama_embed_model=settings.OLLAMA_EMBED_MODEL,
            ollama_embed_api_base=settings.OLLAMA_API_BASE,
            ollama_embed_timeout=settings.OLLAMA_EMBED_TIMEOUT,
        )
        retrieval_results = retriever.retrieve(user_input)
        
        retrieval_summary = {
            "rag": retriever.get_backend_summary(),
            "total_chunks": len(all_chunks),
            "retrieved_chunks": len(retrieval_results),
            "results": retrieval_results
        }
        self.artifact_manager.save_json_artifact("03_retrieval_results.json", retrieval_summary)
        tool_ledger.record(
            "context_retrieve",
            {
                "query": user_input,
                "backend": settings.RAG_BACKEND,
                "top_k": settings.RETRIEVAL_TOP_K,
            },
            {
                "total_chunks": len(all_chunks),
                "retrieved_chunks": len(retrieval_results),
                "retrieved_files": len({item.get("relative_path") for item in retrieval_results}),
                "rag": retriever.get_backend_summary(),
            },
        )
        
        # ========== Stage 6-7: Prompt / LLM ==========
        multi_agent_result = None
        if mode == "multi":
            self.logger.info("[Stage 6] 启动多智能体协同")
            coordinator = MultiAgentCoordinator(
                provider=self.provider_override,
                model=self.model_override,
                temperature=self.temperature_override,
                max_revision_rounds=self.max_review_rounds,
            )
            multi_agent_result = coordinator.run(
                task_type=task_plan.task_type.value,
                language=task_plan.language.value,
                user_query=user_input,
                analysis_info=analysis_output,
                retrieval_results=retrieval_results,
                previous_response=previous_context.llm_output_summary if previous_context else None,
                previous_retrieval_summary=previous_context.retrieval_summary if previous_context else None,
            )
            llm_response = {
                "response": multi_agent_result["final_response"],
                "model": multi_agent_result["llm_config"]["model"],
                "stop_reason": multi_agent_result["review"]["verdict"],
                "usage": {},
            }
            analysis_output["llm_config"] = {
                "provider": multi_agent_result["llm_config"]["provider"],
                "model": multi_agent_result["llm_config"]["model"],
            }
            self.artifact_manager.save_artifact(
                "04_prompt.txt",
                "multi-agent mode\nsee 04_multi_agent_trace.md / 04_multi_agent_trace.json",
            )
            self.artifact_manager.save_json_artifact("04_multi_agent_trace.json", multi_agent_result)
            self.artifact_manager.save_artifact(
                "04_multi_agent_trace.md",
                coordinator.render_trace_markdown(multi_agent_result),
            )
        else:
            prompt_builder = PromptBuilder(task_plan.task_type.value, task_plan.language.value)
            
            system_prompt = prompt_builder.build_system_prompt()
            user_prompt = prompt_builder.build_user_prompt(
                user_input,
                retrieval_results,
                analysis_output,
                previous_response=previous_context.llm_output_summary if previous_context else None,
                previous_retrieval_summary=previous_context.retrieval_summary if previous_context else None,
            )
            
            self.artifact_manager.save_artifact("04_prompt.txt", f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n=== USER PROMPT ===\n{user_prompt}")
            
            self.logger.info("[Stage 7] 启动单智能体调用")
            llm_client = self._create_llm_client()
            llm_response = llm_client.call(system_prompt, user_prompt)
            analysis_output["llm_config"] = {
                "provider": llm_client.provider,
                "model": llm_client.model,
                "api_base": llm_client.api_base,
            }

        tool_ledger.record(
            "llm_generate",
            {
                "mode": mode,
                "task_type": task_plan.task_type.value,
                "language": task_plan.language.value,
            },
            {
                "provider": (analysis_output.get("llm_config") or {}).get("provider"),
                "model": (analysis_output.get("llm_config") or {}).get("model"),
                "stop_reason": llm_response.get("stop_reason"),
                "response_chars": len(llm_response.get("response", "")),
                "agent_steps": len((multi_agent_result or {}).get("steps", [])),
            },
        )

        self.artifact_manager.save_json_artifact("02_analysis.json", analysis_output)
        self.artifact_manager.save_artifact("05_llm_response.md", llm_response["response"])
        
        # ========== Stage 8: 结果处理 ==========
        self.logger.info(f"[Stage 8] 解析 LLM 输出")
        extraction_language = (
            CodeChunker.detect_language(Path(apply_file), task_plan.language.value)
            if apply_file
            else task_plan.language.value
        )
        extracted_code_blocks = ResultFormatter.extract_code_blocks(
            llm_response["response"],
            extraction_language,
        )
        self.artifact_manager.save_json_artifact(
            "06_extracted_code.json",
            {
                "count": len(extracted_code_blocks),
                "code_blocks": extracted_code_blocks,
            }
        )
        tool_ledger.record(
            "code_extract",
            {
                "language": extraction_language,
                "response_chars": len(llm_response.get("response", "")),
            },
            {
                "code_block_count": len(extracted_code_blocks),
            },
        )
        apply_result = None
        if apply_file:
            self.logger.info(f"[Stage 8] 尝试将生成代码写回文件 | file={apply_file}")
            apply_result, validation_result = self._apply_with_lifecycle(
                workspace_path=workspace_path,
                apply_file=apply_file,
                language=task_plan.language.value,
                extracted_code_blocks=extracted_code_blocks,
                llm_response=llm_response,
                validate=validate,
                validation_mode=validation_mode,
                validate_cmd=validate_cmd,
                rollback_on_failure=rollback_on_failure,
            )
            self.artifact_manager.save_json_artifact("08_apply_result.json", apply_result)
            tool_ledger.record(
                "patch_apply",
                {
                    "file": apply_file,
                    "validate": validate,
                    "rollback_on_failure": rollback_on_failure,
                },
                {
                    "status": apply_result.get("status"),
                    "file": apply_result.get("file"),
                    "reason": apply_result.get("reason"),
                    "diff_stats": apply_result.get("diff_stats"),
                },
                status="success" if apply_result.get("status") not in {"rollback_failed"} else "error",
            )
            if apply_result.get("rollback_output"):
                tool_ledger.record(
                    "rollback",
                    {"file": apply_result.get("file")},
                    apply_result.get("rollback_output") or {},
                    status=(
                        "success"
                        if (apply_result.get("rollback_output") or {}).get("status") == "success"
                        else "skipped"
                    ),
                )

        # ========== Stage 9: 验证 ==========
        validation_result = None
        if apply_result and apply_result.get("validation_output"):
            validation_result = apply_result["validation_output"]
        elif validate:
            validation_result = self._run_validation(
                workspace_path=workspace_path,
                language=task_plan.language.value,
                validation_mode=validation_mode,
                validate_cmd=validate_cmd,
            )

        if validation_result:
            self.artifact_manager.save_json_artifact(
                "07_validation_output.json",
                validation_result
            )
            tool_ledger.record(
                "validate",
                {
                    "validation_mode": validation_mode,
                    "validate_cmd": validate_cmd,
                    "language": task_plan.language.value,
                },
                {
                    "success": validation_result.get("success"),
                    "source": validation_result.get("source"),
                    "stage": validation_result.get("stage"),
                    "exit_code": validation_result.get("exit_code"),
                    "timed_out": validation_result.get("timed_out"),
                    "skipped_reason": validation_result.get("skipped_reason"),
                },
                status="success" if validation_result.get("success") else "failed",
            )
        
        # ========== Stage 10: 结果输出 ==========
        self.logger.info(f"[Stage 10] 结果输出与会话保存")
        
        result = {
            "session_id": current_session_id,
            "parent_session_id": previous_session_id,
            "task_type": task_plan.task_type.value,
            "language": task_plan.language.value,
            "user_query": user_input,
            "execution_mode": mode,
            "llm_response": llm_response["response"],
            "llm_config": analysis_output.get("llm_config"),
            "multi_agent": multi_agent_result,
            "apply_output": apply_result,
            "validation_output": validation_result,
        }

        evaluation_output = RunMetricsEvaluator().evaluate_run(
            user_query=user_input,
            retrieval_summary=retrieval_summary,
            extracted_code_blocks=extracted_code_blocks,
            apply_output=apply_result,
            validation_output=validation_result,
            analysis_output=analysis_output,
            execution_mode=mode,
            tool_calls=tool_ledger.to_dict(),
        )
        result["evaluation_output"] = evaluation_output
        self.artifact_manager.save_json_artifact("10_evaluation.json", evaluation_output)
        
        # 保存结果摘要
        summary = ResultFormatter.generate_summary(task_plan.task_type.value, result)
        self.artifact_manager.save_artifact("09_result.md", summary)
        self._save_delivery_artifacts(
            result=result,
            analysis_output=analysis_output,
            retrieval_summary=retrieval_summary,
            tool_ledger=tool_ledger,
        )
        
        # 保存 session 上下文（便于 follow-up）
        session_context = SessionContext(
            session_id=current_session_id,
            task_type=task_plan.task_type.value,
            language=task_plan.language.value,
            workspace_root=workspace_root,
            user_query=user_input,
            created_at=datetime.now().isoformat(),
            parent_session_id=previous_session_id,
            retrieval_summary=str(retrieval_summary),
            llm_output_summary=llm_response["response"][:500],
        )
        
        self.session_manager.save_session(session_context, session_dir)
        
        self.logger.info(f"=" * 60)
        self.logger.info(f"执行完成！" )
        self.logger.info(f"Session 目录: {session_dir}")
        self.logger.info(f"=" * 60)
        
        print("\n" + summary)
        
        return result


@click.command()
@click.option(
    "--workspace",
    "--repo",
    "-w",
    "workspace",
    required=True,
    help="目标项目的根目录路径"
)
@click.option(
    "--query",
    "--task",
    "-q",
    "query",
    required=True,
    help="用户需求或问题（自然语言）"
)
@click.option(
    "--session-id",
    "-s",
    default=None,
    help="上一轮的 session ID（用于继续追问）"
)
@click.option(
    "--no-validate",
    is_flag=True,
    default=False,
    help="是否跳过验证步骤"
)
@click.option(
    "--provider",
    default=None,
    help="覆盖使用的 LLM Provider（如 openai / groq / ollama / aicanapi）"
)
@click.option(
    "--model",
    default=None,
    help="覆盖使用的模型名"
)
@click.option(
    "--temperature",
    type=float,
    default=None,
    help="覆盖温度参数"
)
@click.option(
    "--apply-file",
    default=None,
    help="将提取出的第一个完整代码块写回到该相对文件路径（保守模式）"
)
@click.option(
    "--self-dev",
    is_flag=True,
    default=False,
    help="允许把平台自身代码作为 workspace 进行自举分析/后续开发辅助"
)
@click.option(
    "--focus-file",
    default=None,
    help="仅聚焦某个文件或目录，减少扫描范围和上下文长度"
)
@click.option(
    "--mode",
    type=click.Choice(["single", "multi"], case_sensitive=False),
    default="single",
    help="执行模式：single 为单智能体，multi 为 planner/implementer/reviewer 协作",
)
@click.option(
    "--validation-mode",
    type=click.Choice(["auto", "local", "docker"], case_sensitive=False),
    default="auto",
    help="验证模式：auto 优先 Docker，失败时降级本地；local 仅本地；docker 仅容器",
)
@click.option(
    "--validate-cmd",
    default=None,
    help="覆盖默认验证命令（例如 'go test ./...'）",
)
@click.option(
    "--rollback-on-failure/--no-rollback-on-failure",
    default=True,
    help="写回后验证失败时是否自动回滚到备份版本",
)
@click.option(
    "--artifacts-keep",
    type=int,
    default=None,
    help="最多保留多少个最近 session；不传则走配置项",
)
@click.option(
    "--artifacts-retention-days",
    type=int,
    default=None,
    help="自动清理多少天前的旧 session；不传则走配置项",
)
def main(
    workspace,
    query,
    session_id,
    no_validate,
    provider,
    model,
    temperature,
    apply_file,
    self_dev,
    focus_file,
    mode,
    validation_mode,
    validate_cmd,
    rollback_on_failure,
    artifacts_keep,
    artifacts_retention_days,
):
    """
    CodeRepair - 代码分析与自动修复研发辅助平台
    
    示例：
        python app.py --workspace /path/to/project --query "修复 bug: 函数返回错误值"
        python app.py -w /path/to/project -q "实现新功能" --session-id 20250330_120000
    """
    try:
        platform = CodeRepairPlatform(
            provider=provider,
            model=model,
            temperature=temperature,
        )
        result = platform.run(
            user_input=query,
            workspace_root=workspace,
            session_id=session_id,
            validate=not no_validate,
            apply_file=apply_file,
            self_dev=self_dev,
            focus_file=focus_file,
            mode=mode.lower(),
            validation_mode=validation_mode.lower(),
            validate_cmd=validate_cmd,
            rollback_on_failure=rollback_on_failure,
            artifacts_keep=artifacts_keep,
            artifacts_retention_days=artifacts_retention_days,
        )
    except Exception as e:
        logger.error(f"平台执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
