import nox


@nox.session(python=["3.9", "3.10"])
def tests(session) -> None:
    session.install("poetry")
    session.run("poetry", "install")
    session.run("coverage", "run", "-m", "pytest")
    session.run("coverage", "report") \


@nox.session
def lint(session) -> None:
    session.install("poetry")
    session.run("poetry", "install")
    session.run("black", "--check", ".")
    session.run("flake8", ".") \


@nox.session
def typing(session) -> None:
    session.install("poetry")
    session.run("poetry", "install")
    session.run("mypy", ".")
