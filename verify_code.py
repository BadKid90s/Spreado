#!/usr/bin/env python3
"""
代码结构验证脚本 - 验证重构后的代码结构
"""

import sys
import ast
from pathlib import Path

def check_file_exists(file_path: str) -> bool:
    """检查文件是否存在"""
    path = Path(file_path)
    if path.exists():
        print(f"✓ {file_path}")
        return True
    else:
        print(f"✗ {file_path} (不存在)")
        return False

def check_python_syntax(file_path: str) -> bool:
    """检查Python文件语法是否正确"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        print(f"✓ {file_path} (语法正确)")
        return True
    except SyntaxError as e:
        print(f"✗ {file_path} (语法错误: {e})")
        return False

def check_class_inheritance(file_path: str, class_name: str, base_class: str) -> bool:
    """检查类是否继承自指定基类"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == base_class:
                        print(f"✓ {class_name} 继承自 {base_class}")
                        return True
        print(f"✗ {class_name} 未继承自 {base_class}")
        return False
    except Exception as e:
        print(f"✗ 检查继承关系失败: {e}")
        return False

def check_abstract_methods(file_path: str, class_name: str, methods: list) -> bool:
    """检查类是否实现了指定的抽象方法"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        class_methods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        class_methods.add(item.name)

        missing_methods = set(methods) - class_methods
        if not missing_methods:
            print(f"✓ {class_name} 实现了所有必需方法")
            return True
        else:
            print(f"✗ {class_name} 缺少方法: {', '.join(missing_methods)}")
            return False
    except Exception as e:
        print(f"✗ 检查抽象方法失败: {e}")
        return False

def main():
    print("=" * 60)
    print("代码结构验证")
    print("=" * 60)

    files_to_check = [
        "uploader/base_uploader.py",
        "uploader/auth_manager.py",
        "utils/base_social_media.py",
        "utils/log.py",
        "uploader/douyin_uploader/uploader.py",
        "uploader/xiaohongshu_uploader/uploader.py",
        "uploader/kuaishou_uploader/uploader.py",
        "uploader/tencent_uploader/uploader.py",
        "cli.py",
        "tests/test_refactored.py",
    ]

    print("\n文件结构检查:")
    print("-" * 60)
    file_results = [check_file_exists(f) for f in files_to_check]

    print("\nPython语法检查:")
    print("-" * 60)
    syntax_results = [check_python_syntax(f) for f in files_to_check]

    print("\n类继承关系检查:")
    print("-" * 60)
    inheritance_checks = [
        ("uploader/douyin_uploader/uploader.py", "DouYinUploader", "BaseUploader"),
        ("uploader/xiaohongshu_uploader/uploader.py", "XiaoHongShuUploader", "BaseUploader"),
        ("uploader/kuaishou_uploader/uploader.py", "KuaiShouUploader", "BaseUploader"),
        ("uploader/tencent_uploader/uploader.py", "TencentUploader", "BaseUploader"),
    ]
    inheritance_results = []
    for file_path, class_name, base_class in inheritance_checks:
        inheritance_results.append(check_class_inheritance(file_path, class_name, base_class))

    print("\n抽象方法实现检查:")
    print("-" * 60)
    abstract_methods = [
        "platform_name",
        "login_url",
        "upload_url",
        "success_url_pattern",
        "login_selectors",
        "upload_video",
    ]
    method_results = []
    for file_path, class_name, _ in inheritance_checks:
        method_results.append(check_abstract_methods(file_path, class_name, abstract_methods))

    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)

    total_files = len(files_to_check)
    passed_files = sum(file_results)
    passed_syntax = sum(syntax_results)
    passed_inheritance = sum(inheritance_results)
    passed_methods = sum(method_results)

    print(f"\n文件检查: {passed_files}/{total_files} 通过")
    print(f"语法检查: {passed_syntax}/{total_files} 通过")
    print(f"继承检查: {passed_inheritance}/{len(inheritance_checks)} 通过")
    print(f"方法检查: {passed_methods}/{len(method_results)} 通过")

    all_passed = (
        passed_files == total_files and
        passed_syntax == total_files and
        passed_inheritance == len(inheritance_checks) and
        passed_methods == len(method_results)
    )

    if all_passed:
        print("\n✓ 所有检查通过！代码结构正确。")
        return 0
    else:
        print("\n✗ 部分检查失败，请检查上述错误。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
