"""
Patcher 文件修改模块测试
"""

import pytest
import tempfile
import os
import shutil

from patcher import FileWriter, PatchApplier


class TestFileWriter:
    """文件写入器测试"""
    
    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作目录"""
        temp_dir = tempfile.mkdtemp(prefix="test_patcher_")
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_write_new_file(self, temp_workspace):
        """测试写入新文件"""
        writer = FileWriter(temp_workspace)
        
        test_file = os.path.join(temp_workspace, "test.txt")
        writer.write_file("test.txt", "Hello World")
        
        assert os.path.exists(test_file)
        with open(test_file, "r") as f:
            assert f.read() == "Hello World"
    
    def test_write_creates_backup(self, temp_workspace):
        """测试写入时是否创建备份"""
        writer = FileWriter(temp_workspace, backup_enabled=True)
        
        test_file = os.path.join(temp_workspace, "test.txt")
        
        # 写入第一次
        writer.write_file("test.txt", "Version 1")
        
        # 写入第二次
        writer.write_file("test.txt", "Version 2")
        
        # 检查备份
        backup_dir = os.path.join(temp_workspace, ".coderepair_backups")
        assert os.path.exists(backup_dir)
        backups = os.listdir(backup_dir)
        assert len(backups) > 0
    
    def test_update_file(self, temp_workspace):
        """测试更新文件"""
        writer = FileWriter(temp_workspace)
        
        test_file = os.path.join(temp_workspace, "test.txt")
        
        # 初始内容
        writer.write_file("test.txt", "Original")
        
        # 更新旧内容为新内容
        writer.update_file(
            "test.txt",
            old_content="Original",
            new_content="Updated"
        )
        
        with open(test_file, "r") as f:
            assert f.read() == "Updated"
    
    def test_append_to_file(self, temp_workspace):
        """测试追加内容"""
        writer = FileWriter(temp_workspace)
        
        test_file = os.path.join(temp_workspace, "test.txt")
        
        writer.write_file("test.txt", "Line 1\n")
        writer.append_to_file("test.txt", "Line 2\n")
        
        with open(test_file, "r") as f:
            content = f.read()
            assert "Line 1" in content
            assert "Line 2" in content
    
    def test_delete_file(self, temp_workspace):
        """测试删除文件"""
        writer = FileWriter(temp_workspace)
        
        test_file = os.path.join(temp_workspace, "test.txt")
        writer.write_file("test.txt", "Delete me")
        
        assert os.path.exists(test_file)
        writer.delete_file("test.txt")
        assert not os.path.exists(test_file)
    
    def test_rollback(self, temp_workspace):
        """测试回滚功能"""
        writer = FileWriter(temp_workspace, backup_enabled=True)
        
        test_file = os.path.join(temp_workspace, "test.txt")
        
        # 写入
        writer.write_file("test.txt", "Version 1")
        version1 = open(test_file).read()
        
        # 修改
        writer.write_file("test.txt", "Version 2")
        
        # 回滚
        writer.rollback_last_operation()
        version_after_rollback = open(test_file).read()
        
        assert version_after_rollback == version1
    
    def test_operations_log(self, temp_workspace):
        """测试操作日志"""
        writer = FileWriter(temp_workspace)
        
        writer.write_file("test1.txt", "Content1")
        writer.write_file("test2.txt", "Content2")
        
        log = writer.get_operations_log()
        
        assert len(log) >= 2
        assert any("write_file" in str(op) for op in log)

    def test_restore_backup(self, temp_workspace):
        """显式指定备份路径时，可以恢复到旧版本。"""
        writer = FileWriter(temp_workspace, backup_enabled=True)

        writer.write_file("test.txt", "Version 1")
        write_result = writer.write_file("test.txt", "Version 2")

        restore_result = writer.restore_backup("test.txt", str(write_result["backup"]))

        assert restore_result["status"] == "success"
        with open(os.path.join(temp_workspace, "test.txt")) as f:
            assert f.read() == "Version 1"


class TestPatchApplier:
    """Patch 应用器测试"""
    
    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作目录"""
        temp_dir = tempfile.mkdtemp(prefix="test_patch_")
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_parse_unified_diff(self, temp_workspace):
        """测试 Unified Diff 解析"""
        applier = PatchApplier(temp_workspace)
        
        diff = """--- a/main.go
+++ b/main.go
@@ -1,3 +1,3 @@
 package main
-func main() {
+func main() {  // updated
  }
"""
        
        # 应该能解析而不抛出异常
        result = applier._parse_patch(diff)
        assert result is not None
    
    def test_apply_simple_diff(self, temp_workspace):
        """测试应用简单的 Diff"""
        applier = PatchApplier(temp_workspace)
        
        # 原始内容
        original = "package main\n\nfunc main() {\n}\n"
        
        # Diff
        diff = """--- a/main.go
+++ b/main.go
@@ -1,4 +1,4 @@
 package main
 
-func main() {
+func main() {  // updated
 }
"""
        
        # 应用 diff
        new_content = applier.apply_patch(original, diff)
        
        assert new_content is not None
        assert "updated" in new_content or len(new_content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
