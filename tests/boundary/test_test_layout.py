"""Guard the test layout: a bare `conftest` import only works by sys.path order (Issue #31)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bare_conftest_imports(source: str) -> list[str]:
    """Imports that resolve through `sys.path` instead of a module this directory owns."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names if alias.name == "conftest"]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "conftest":
            found.append("from conftest import ...")
    return found


def test_the_detector_recognises_bare_conftest_imports() -> None:
    assert bare_conftest_imports("from conftest import helper\n") == ["from conftest import ..."]
    assert bare_conftest_imports("import conftest\n") == ["conftest"]
    assert bare_conftest_imports("import conftest as c, os\n") == ["conftest"]
    # 提到这个名字不算：注释与 docstring 都不是 Import 节点。
    assert bare_conftest_imports('"""from conftest import helper"""\n') == []
    assert bare_conftest_imports("# import conftest\nimport os\n") == []
    # 显式相对导入靠包名定位，与 `sys.path` 顺序无关。
    assert bare_conftest_imports("from .conftest import helper\n") == []
    assert bare_conftest_imports("from fixtures import helper\n") == []


def test_no_test_module_imports_conftest_by_bare_name() -> None:
    offenders = {}
    for path in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        hits = bare_conftest_imports(path.read_text(encoding="utf-8"))
        if hits:
            offenders[str(path.relative_to(ROOT))] = hits
    assert not offenders, (
        "裸 `conftest` 导入只因为「同目录的 conftest 恰好是 sys.path 上第一个叫这个名字的模块」才成立；"
        "任何新增维度目录只要放 conftest.py（如 tests/performance/conftest.py）就会顶掉它，"
        "让 tests/adversarial / tests/functional 的既有用例报 ImportError（Issue #31，实测 8 条失败）。"
        "共享辅助对象要放进该维度独有的模块名，例如 tests/functional/acceptance.py，再显式导入；"
        f"违规处：{offenders}"
    )
