"""
CodeRepair 演示脚本

这个脚本展示了如何使用 CodeRepair 平台的完整流程
"""
import sys
import time
from pathlib import Path

# 添加上级目录到路径（便于导入）
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logger import get_logger

logger = get_logger(__name__)


def demo_workflow():
    """演示完整的 CodeRepair 工作流程"""
    
    logger.info("=" * 60)
    logger.info("CodeRepair 演示流程")
    logger.info("=" * 60)
    
    # 演示 1: 任务分类
    logger.info("\n【演示 1】 任务分类")
    logger.info("-" * 40)
    
    from core.planner import TaskPlanner
    
    planner = TaskPlanner()
    
    queries = [
        "修复函数返回值错误的 bug",
        "实现一个新的用户认证模块",
        "代码审查：这段并发代码是否安全？"
    ]
    
    for query in queries:
        task_type = planner.classify_task(query)
        logger.info(f"  查询: {query}")
        logger.info(f"  分类结果: {task_type.value}\n")
    
    # 演示 2: 路径过滤
    logger.info("\n【演示 2】 路径过滤 - 防止 RAG 污染")
    logger.info("-" * 40)
    
    from retrieval.filters import PathFilter
    
    sample_project = Path(__file__).parent / "sample_go_project"
    platform_root = Path(__file__).parent.parent
    
    path_filter = PathFilter(
        platform_root=platform_root,
        workspace_root=sample_project,
        exclude_patterns=[".*", "__pycache__", ".venv", "artifacts"],
        include_extensions=[".go"]
    )
    
    logger.info(f"  平台根目录: {platform_root.name}/")
    logger.info(f"  项目根目录: {sample_project.name}/")
    logger.info(f"  排除规则激活：防止平台代码混入检索\n")
    
    # 演示 3: 仓库扫描
    logger.info("\n【演示 3】 仓库扫描")
    logger.info("-" * 40)
    
    from retrieval.scanner import RepositoryScanner
    
    scanner = RepositoryScanner(path_filter)
    scan_result = scanner.scan()
    
    logger.info(f"  扫描完成:")
    logger.info(f"    - 总文件数: {scan_result['total_files']}")
    logger.info(f"    - Go 文件: {scan_result['go_files']}")
    logger.info(f"    - Python 文件: {scan_result['py_files']}\n")
    
    # 演示 4: Go AST 分析
    logger.info("\n【演示 4】 Go 代码结构分析")
    logger.info("-" * 40)
    
    from analyzers.go_ast import GoAnalyzer
    
    analyzer = GoAnalyzer()
    
    # 如果有检索到 Go 文件就分析，否则显示示例
    if scan_result["go_files_list"]:
        for file_path in scan_result["go_files_list"][:2]:
            analysis = analyzer.analyze_file(file_path)
            logger.info(f"  文件: {file_path.name}")
            logger.info(f"    - 包名: {analysis.get('package', 'N/A')}")
            logger.info(f"    - 导入数: {len(analysis.get('imports', []))}")
            logger.info(f"    - 函数数: {len(analysis.get('functions', []))}")
            logger.info(f"    - 类型定义: {analysis.get('types', [])}\n")
    else:
        logger.info("  (未检索到 Go 文件，显示示例分析结果)")
        logger.info("  文件: main.go")
        logger.info("    - 包名: main")
        logger.info("    - 导入数: 2")
        logger.info("    - 函数数: 3")
        logger.info("    - 类型定义: ['User', 'Config']\n")
    
    # 演示 5: Prompt 组装
    logger.info("\n【演示 5】 Prompt 组装")
    logger.info("-" * 40)
    
    from llm.prompt_builder import PromptBuilder
    
    builder = PromptBuilder("bug_fix", "go")
    
    system_prompt = builder.build_system_prompt()
    user_prompt = builder.build_user_prompt(
        "修复 Calculate 函数的计算错误",
        retrieval_results=[
            {
                "relative_path": "main.go",
                "start_line": 45,
                "end_line": 52,
                "text": "func (u *User) Calculate(x int) int {\n    // ...\n    return result - 1  // BUG!\n}",
                "summary": "Calculate 函数"
            }
        ]
    )
    
    logger.info(f"  系统提示长度: {len(system_prompt)} 字符")
    logger.info(f"  用户提示长度: {len(user_prompt)} 字符")
    logger.info(f"  Prompt 已准备就绪\n")
    
    # 演示 6: 验证执行
    logger.info("\n【演示 6】 验证执行 - Go Build")
    logger.info("-" * 40)
    
    from executors.validator import Validator
    
    validator = Validator(sample_project)
    
    logger.info(f"  在目录 {sample_project.name} 中执行 go build...\n")
    result = validator.run_go_build()
    
    logger.info(f"  执行结果:")
    logger.info(f"    - Source: {result.source}")
    logger.info(f"    - Stage: {result.stage}")
    logger.info(f"    - Exit Code: {result.exit_code}")
    logger.info(f"    - Success: {result.success}")
    if result.stderr:
        logger.warning(f"    - Error: {result.stderr[:100]}\n")
    else:
        logger.info(f"    - 构建成功\n")
    
    # 演示 7: 会话管理
    logger.info("\n【演示 7】 会话管理（多轮对话）")
    logger.info("-" * 40)
    
    from core.session import SessionManager, SessionContext
    from config import settings
    from datetime import datetime
    
    session_manager = SessionManager(settings.ARTIFACTS_ROOT)
    session_id = session_manager.create_session_id()
    
    logger.info(f"  生成 Session ID: {session_id}")
    logger.info(f"  第二轮时可以用这个 ID 继续追问")
    logger.info(f"  Session 信息会被保存，便于后续调用\n")
    
    # 演示 8: Artifacts 管理
    logger.info("\n【演示 8】 Artifacts 管理")
    logger.info("-" * 40)
    
    from outputs.artifact_manager import ArtifactManager
    
    artifact_mgr = ArtifactManager(settings.ARTIFACTS_ROOT)
    session_dir = artifact_mgr.create_session(session_id)
    
    logger.info(f"  创建 Session 目录: {session_dir}")
    logger.info(f"  所有中间结果都会保存到此目录:")
    logger.info(f"    - 01_input.txt: 用户输入")
    logger.info(f"    - 02_analysis.json: 任务分析")
    logger.info(f"    - 03_retrieval_results.json: 检索结果")
    logger.info(f"    - 04_prompt.txt: 发送给 LLM 的 prompt")
    logger.info(f"    - 05_llm_response.md: LLM 输出")
    logger.info(f"    - 06_extracted_code.json: 提取出的代码块")
    logger.info(f"    - 09_result.md: 最终结果摘要")
    logger.info(f"    - runner.log: 完整的运行日志\n")
    
    logger.info("=" * 60)
    logger.info("演示完成！")
    logger.info("=" * 60)
    logger.info("\n进阶体验：")
    logger.info(f"  cd {Path(__file__).parent.parent}")
    logger.info(f"  ./.venv/bin/python app.py --workspace {sample_project} \\")
    logger.info(f"    --query '修复 Calculate 函数返回值错误' --validation-mode auto")
    logger.info("")


if __name__ == "__main__":
    demo_workflow()
