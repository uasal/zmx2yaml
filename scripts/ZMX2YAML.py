#!/usr/bin/env python

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from zmx2batoid import ZMX2YAML

logger = logging.getLogger(__name__)
formatter = logging.Formatter("%(asctime)s - %(name)s - L%(lineno)s - %(levelname)s - %(message)s")
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.setLevel("DEBUG")


def main():
    """
    This script is used to create YAML file from Zemax prescription data.

    It should be run from the version directory level, meaning the mapping
    file will be at the same level.

    Examples
    --------
    >>> python ZMX2YAML.py STP.txt 7 8 9 11 STP --enpp 3 --field_bias 5

    Script that creates YAML file from Zemax prescription data TXT file.

    Parameters
    ----------
    arg1 : str
        Path to the input file.

    arg2 : list of int or str
        Surface numbers to be modeled (excluding the IMA surface).

    arg3 : str
        Path to the output file.

    arg4 : list of int or str, optional
        Surface numbers representing the entrance pupil.  Default is an empty list.

    arg5 : list of int or str, optional
        Surface numbers representing the field bias.  Default is an empty list.

    Output:
    -------
    """

    logger.debug("Starting ZMX2YAML script...")

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "prd_file_name",
        type=str,
        help="Name of input file. Only .txt files are supported",
    )
    parser.add_argument(
        "wanted_surf_list",
        nargs='+', # One or more arguments (required)
        help="List of surface numbers to be modeled (w/o IMA surface). Space-separated. Could be list of int or str.",
    )
    parser.add_argument(
        "yaml_file_name",
        type=str,
        help="Name of output file.",
    )
    parser.add_argument(
        "--enpp",
        nargs='*', # Zero or more arguments (optional)
        default=[],
        help="Optional list of entrance pupil surface numbers. Space-separated list of int or str.",
    )
    parser.add_argument(
        "--field_bias",
        nargs='*', # Zero or more arguments (optional)
        default=[],
        help="Optional list of field bias surface numbers. Space-separated list of int or str.",
    )

    args = parser.parse_args()

    logger.info(f"{args=}")
    
    supported_types = ["txt"]
    file_ext = Path(args.prd_file_name).suffix.lower().lstrip(".")
    if file_ext not in supported_types:
        raise OSError(f"File type of {file_ext} is not supported. Must be one of: {supported_types}.")
    
    if isinstance(args.yaml_file_name, str) or isinstance(args.yaml_file_name, Path):
        yaml_file_name = str(args.yaml_file_name)
    else:
        raise OSError(f"File name {args.yaml_file_name} is not supported.")
    
    wanted_surf_list = parse_intable_list(args.wanted_surf_list)
    enpp = parse_intable_list(args.enpp)
    field_bias = parse_intable_list(args.field_bias)

    logger.info(f"Processing file: {args.prd_file_name}")

    ZMX2YAML(
        prd_file_name=args.prd_file_name,
        wanted_surf_list=wanted_surf_list,
        enpp=enpp,
        field_bias=field_bias
        ).write_yaml(yaml_file_name)
    
    logger.info(f"File created: {yaml_file_name}.yaml")


def parse_intable_list(values):
    result = []
    for v in values:
        try:
            result.append(int(v))
        except ValueError:
            raise ValueError(f"Value '{v}' is not an integer or a string representing an integer.")
    return result


if __name__ == "__main__":
    main()