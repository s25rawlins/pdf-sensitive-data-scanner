"""
Nox configuration for automated testing and development tasks.

This module defines sessions for running tests, linting, type checking,
and other development workflows in isolated environments.
"""

import nox
from pathlib import Path

PYTHON_VERSIONS = ["3.12"]

SOURCE_FILES = ["app", "tests", "noxfile.py"]

DEV_DEPENDENCIES = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "httpx>=0.25.2",
]

LINT_DEPENDENCIES = [
    "black>=23.11.0",
    "flake8>=6.1.0",
    "isort>=5.12.0",
    "mypy>=1.7.0",
]


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    session.install("-r", "requirements.txt")
    session.install(*DEV_DEPENDENCIES)
    
    args = session.posargs or [
        "tests",
        "--cov=app",
        "--cov-report=html",
        "--cov-report=term",
        "--cov-report=xml",
        "-v",
    ]
    session.run("pytest", *args)


@nox.session(python=["3.11"])
def test_unit(session: nox.Session) -> None:
    """Run only unit tests (fast tests)."""
    session.install("-r", "requirements.txt")
    session.install(*DEV_DEPENDENCIES)
    
    session.run(
        "pytest",
        "tests/test_detector.py",
        "tests/test_pdf_processor.py",
        "-v",
        "--tb=short",
    )


@nox.session(python=["3.11"])
def test_integration(session: nox.Session) -> None:
    """Run integration tests (requires external services)."""
    session.install("-r", "requirements.txt")
    session.install(*DEV_DEPENDENCIES)
    
    session.env["CLICKHOUSE_HOST"] = session.env.get("CLICKHOUSE_HOST", "localhost")
    session.env["CLICKHOUSE_PORT"] = session.env.get("CLICKHOUSE_PORT", "9000")
    
    session.run(
        "pytest",
        "tests/test_api.py",
        "-v",
        "--tb=short",
        "-m",
        "integration",
    )


@nox.session(python=["3.11"])
def lint(session: nox.Session) -> None:
    """Run linters on the codebase."""
    session.install(*LINT_DEPENDENCIES)
    
    session.run("black", "--check", "--diff", *SOURCE_FILES)
    session.run("isort", "--check-only", "--diff", *SOURCE_FILES)
    session.run("flake8", *SOURCE_FILES)


@nox.session(python=["3.11"])
def format(session: nox.Session) -> None:
    """Format code with black and isort."""
    session.install("black", "isort")
    
    session.run("black", *SOURCE_FILES)
    session.run("isort", *SOURCE_FILES)


@nox.session(python=["3.11"])
def type_check(session: nox.Session) -> None:
    """Run type checking with mypy."""
    session.install("-r", "requirements.txt")
    session.install("mypy", "types-PyYAML")
    
    session.run("mypy", "app", "--ignore-missing-imports")


@nox.session(python=["3.11"])
def safety(session: nox.Session) -> None:
    """Check for security vulnerabilities in dependencies."""
    session.install("safety")
    
    session.run("safety", "check", "--file=requirements.txt")


@nox.session(python=["3.11"])
def docs(session: nox.Session) -> None:
    """Generate documentation."""
    session.install("sphinx", "sphinx-autodoc-typehints", "sphinx-rtd-theme")
    session.install("-r", "requirements.txt")
    
    session.cd("docs")
    session.run("sphinx-build", "-b", "html", "source", "build/html")


@nox.session(python=["3.11"])
def dev(session: nox.Session) -> None:
    """Create development environment with all dependencies."""
    session.install("-r", "requirements.txt")
    session.install(*DEV_DEPENDENCIES)
    session.install(*LINT_DEPENDENCIES)
    session.install("ipython", "ipdb")
    
    session.log("Development environment ready!")
    session.log("Run 'nox -s serve' to start the development server")


@nox.session(python=["3.11"])
def serve(session: nox.Session) -> None:
    """Run the development server."""
    session.install("-r", "requirements.txt")
    
    session.env["ENV"] = "development"
    session.run(
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    )


@nox.session(python=["3.11"])
def coverage_report(session: nox.Session) -> None:
    """Generate and display coverage report."""
    session.install("coverage[toml]")
    
    session.run("coverage", "html")
    session.run("coverage", "report", "--fail-under=80")
    
    import webbrowser
    coverage_file = Path("htmlcov/index.html").absolute()
    if coverage_file.exists():
        webbrowser.open(f"file://{coverage_file}")


@nox.session(python=["3.11"])
def clean(session: nox.Session) -> None:
    """Clean up temporary files and build artifacts."""
    patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        ".coverage",
        "htmlcov",
        ".pytest_cache",
        ".mypy_cache",
        "*.egg-info",
        "dist",
        "build",
        ".nox",
    ]
    
    for pattern in patterns:
        session.log(f"Removing {pattern}")
        for path in Path(".").glob(pattern):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                import shutil
                shutil.rmtree(path)


nox.options.sessions = ["tests", "lint", "type_check"]  # Default sessions
nox.options.reuse_existing_virtualenvs = True  # Faster subsequent runs