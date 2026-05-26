import argparse
import sys

from .compiler import Compiler


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="xdrs-compiler",
        description="Compile documents into XDRS elements.",
    )
    parser.add_argument("source_dir", help="Directory containing source documents")
    parser.add_argument("output_dir", help="Directory to write compiled XDRS elements")
    args = parser.parse_args()

    compiler = Compiler(source_dir=args.source_dir, output_dir=args.output_dir)
    result = compiler.compile()
    print(result.summary())
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
