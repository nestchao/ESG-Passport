"""Command line interface. Generation is offline and refuses existing output folders."""
import argparse
import json
from .generate import generate
from .validate import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('generate', help='Create a new paired dataset')
    create.add_argument('--output', required=True)
    create.add_argument('--font-dir', required=True, help='Directory containing Arial/Courier New TTF fonts')
    create.add_argument('--bases-per-family', type=int, default=15, choices=range(1, 16))
    create.add_argument('--wear', choices=['none', 'light', 'moderate'], default='none')
    check = commands.add_parser('validate', help='Validate an existing paired dataset')
    check.add_argument('dataset')
    args = parser.parse_args()
    try:
        if args.command == 'generate':
            result = generate(args.output, args.font_dir, bases_per_family=args.bases_per_family, wear=args.wear)
            result = {key: result[key] for key in ('image_count', 'base_documents', 'category_counts', 'wear')}
        else:
            result = validate(args.dataset)
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
