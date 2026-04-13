import ast
import sys
from pathlib import Path


def parse_file(path: str | Path) -> ast.Module:
    source = Path(path).read_text(encoding="utf-8")
    return ast.parse(source, filename=str(path))


def walk(tree: ast.AST):
    """Yield every node in the tree (breadth-first via ast.walk)."""
    yield from ast.walk(tree)


def visit(tree: ast.AST, visitor: ast.NodeVisitor) -> None:
    """Run a NodeVisitor subclass over the tree."""
    visitor.visit(tree)


class FunctionCollector(ast.NodeVisitor):
    """Example visitor: collects all function/method definitions."""

    def __init__(self):
        self.functions: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions.append({"name": node.name, "line": node.lineno})
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


class ImportCollector(ast.NodeVisitor):
    """Example visitor: collects all import statements."""

    def __init__(self):
        self.imports: list[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")


class BannedWordError(Exception):
    pass


class BannedWordChecker(ast.NodeVisitor):
    """Raises BannedWordError on the first banned word found in identifiers or string literals."""

    def __init__(self, banned: set[str]):
        self._banned = {w.lower() for w in banned}
        self._violations: list[tuple[str, int]] = []

    def _check(self, word: str, lineno: int):
        if word.lower() in self._banned:
            self._violations.append((word, lineno))

    def visit_Name(self, node: ast.Name):
        self._check(node.id, node.lineno)

    def visit_Attribute(self, node: ast.Attribute):
        self._check(node.attr, node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check(node.name, node.lineno)
        for arg in node.args.args:
            self._check(arg.arg, node.lineno)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        self._check(node.name, node.lineno)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str):
            for word in node.value.split():
                self._check(word.strip(".,!?;:\"'"), node.lineno)

    def check(self, tree: ast.AST) -> list[tuple[str, int]]:
        """Return all (word, lineno) violations found in *tree*."""
        self.visit(tree)
        return self._violations


class FlowPrinter(ast.NodeVisitor):
    """Prints the structural flow of a module: imports, classes, functions,
    and control-flow statements with indented nesting.

    If *banned_words* is provided, raises BannedWordError listing every
    violation before printing anything.
    """

    _INDENT = "  "

    def __init__(self, banned_words: set[str] | list[str] | None = None):
        self._depth = 0
        self._banned = set(banned_words) if banned_words else set()

    def _line(self, text: str, lineno: int | None = None):
        loc = f"  \033[2m(line {lineno})\033[0m" if lineno else ""
        print(f"{self._INDENT * self._depth}{text}{loc}")

    def _enter(self, text: str, lineno: int | None = None):
        self._line(text, lineno)
        self._depth += 1

    def _exit(self):
        self._depth -= 1

    # ── top-level statements ────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import):
        names = ", ".join(a.name for a in node.names)
        self._line(f"import {names}", node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        names = ", ".join(a.name for a in node.names)
        self._line(f"from {node.module} import {names}", node.lineno)

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = ", ".join(_name(b) for b in node.bases)
        label = f"class {node.name}" + (f"({bases})" if bases else "")
        self._enter(f"\033[1;34m{label}\033[0m", node.lineno)
        for stmt in node.body:
            self.visit(stmt)
        self._exit()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        args = ", ".join(a.arg for a in node.args.args)
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        decorators = "".join(f"@{_name(d)} " for d in node.decorator_list)
        self._enter(f"\033[1;32m{decorators}{prefix} {node.name}({args})\033[0m", node.lineno)
        for stmt in node.body:
            self.visit(stmt)
        self._exit()

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── control flow ────────────────────────────────────────────────────────

    def visit_If(self, node: ast.If):
        self._enter(f"\033[33mif\033[0m {ast.unparse(node.test)}", node.lineno)
        for stmt in node.body:
            self.visit(stmt)
        self._exit()
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                # elif
                self._enter(f"\033[33melif\033[0m {ast.unparse(node.orelse[0].test)}", node.orelse[0].lineno)
                for stmt in node.orelse[0].body:
                    self.visit(stmt)
                self._exit()
                if node.orelse[0].orelse:
                    self._enter(f"\033[33melse\033[0m", node.lineno)
                    for stmt in node.orelse[0].orelse:
                        self.visit(stmt)
                    self._exit()
            else:
                self._enter(f"\033[33melse\033[0m", node.lineno)
                for stmt in node.orelse:
                    self.visit(stmt)
                self._exit()

    def visit_For(self, node: ast.For):
        self._enter(f"\033[33mfor\033[0m {ast.unparse(node.target)} in {ast.unparse(node.iter)}", node.lineno)
        for stmt in node.body:
            self.visit(stmt)
        self._exit()

    def visit_While(self, node: ast.While):
        self._enter(f"\033[33mwhile\033[0m {ast.unparse(node.test)}", node.lineno)
        for stmt in node.body:
            self.visit(stmt)
        self._exit()

    def visit_With(self, node: ast.With):
        items = ", ".join(ast.unparse(i) for i in node.items)
        self._enter(f"\033[33mwith\033[0m {items}", node.lineno)
        for stmt in node.body:
            self.visit(stmt)
        self._exit()

    def visit_Try(self, node: ast.Try):
        self._enter(f"\033[33mtry\033[0m", node.lineno)
        for stmt in node.body:
            self.visit(stmt)
        self._exit()
        for handler in node.handlers:
            exc = ast.unparse(handler.type) if handler.type else "*"
            name = f" as {handler.name}" if handler.name else ""
            self._enter(f"\033[33mexcept\033[0m {exc}{name}", handler.lineno)
            for stmt in handler.body:
                self.visit(stmt)
            self._exit()
        if node.finalbody:
            self._enter(f"\033[33mfinally\033[0m", node.lineno)
            for stmt in node.finalbody:
                self.visit(stmt)
            self._exit()

    # ── expressions ─────────────────────────────────────────────────────────

    def visit_Call(self, node: ast.Call):
        self._line(f"call {ast.unparse(node)}", node.lineno)

    def visit_Return(self, node: ast.Return):
        val = ast.unparse(node.value) if node.value else ""
        self._line(f"\033[35mreturn\033[0m {val}", node.lineno)

    def visit_Assign(self, node: ast.Assign):
        targets = ", ".join(ast.unparse(t) for t in node.targets)
        self._line(f"{targets} = {ast.unparse(node.value)}", node.lineno)

    def visit_Expr(self, node: ast.Expr):
        # bare expression statements (e.g. standalone calls)
        if isinstance(node.value, ast.Call):
            self.visit_Call(node.value)
        else:
            self._line(ast.unparse(node), node.lineno)

    def visit_Raise(self, node: ast.Raise):
        val = ast.unparse(node.exc) if node.exc else ""
        self._line(f"\033[31mraise\033[0m {val}", node.lineno)


def _name(node: ast.expr) -> str:
    """Best-effort name extraction from an expression node."""
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def print_flow(path: str | Path, banned_words: set[str] | list[str] | None = None) -> None:
    """Parse *path* and print its structural flow to stdout.

    Raises BannedWordError before printing if any banned word is found.
    """
    tree = parse_file(path)
    if banned_words:
        violations = BannedWordChecker(set(banned_words)).check(tree)
        if violations:
            details = "\n".join(f"  line {lineno}: '{word}'" for word, lineno in violations)
            raise BannedWordError(f"{path} contains banned words:\n{details}")
    print(f"\033[1mFlow: {path}\033[0m")
    FlowPrinter(banned_words).visit(tree)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Print AST flow of a Python file.")
    parser.add_argument("file", help="Path to .py file")
    parser.add_argument("--ban", metavar="WORD", nargs="+", default=[], help="Banned words")
    args = parser.parse_args()
    print_flow(args.file, banned_words=args.ban)
