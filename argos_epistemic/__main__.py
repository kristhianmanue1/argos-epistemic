import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version


def _package_version() -> str:
    try:
        return version("argos-epistemic")
    except PackageNotFoundError:
        return "desconocida (checkout sin instalar)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m argos_epistemic",
        add_help=False,
        description=(
            "Argos Epistemic es una biblioteca Python para análisis de software "
            "con evidencia trazable, presupuesto explícito y conclusiones auditables."
        ),
        epilog=(
            "Esta interfaz sólo ofrece descubrimiento y versión; no analiza repositorios. "
            "Usa analyze_path() o analyze_system() desde Python. Documentación: "
            "https://github.com/kristhianmanue1/argos-epistemic#uso-mínimo"
        ),
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="muestra esta ayuda y termina",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
        help="muestra la versión instalada y termina",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
