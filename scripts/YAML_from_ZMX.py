#!/usr/bin/env python

import argparse
import logging
import sys
from pathlib import Path

from zmx2yaml import ZMX2YAML

logger = logging.getLogger(__name__)
formatter = logging.Formatter("%(asctime)s - %(name)s - L%(lineno)s - %(levelname)s - %(message)s")
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.setLevel("INFO")


def main():
    """
    This script is used to create YAML file from Zemax prescription data.

    From the command line run the following to see the description and parameter descriptions.

    "python3 scripts/YAML_from_ZMX.py -h:
    """

    logger.debug("Starting ZMX2YAML script...")

    description = """
    This script is used to create YAML file from Zemax prescription data.\n

    It should be run from the version directory level, meaning the mapping
    file will be at the same level.\n

    Examples
    --------
    >>> python3 scripts/YAML_from_ZMX.py tests/test_data/Ultramarine_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt 7 8 9 11 tests/test_data/UM.yaml --enpp 3 --field_bias 5
    >>> python3 scripts/YAML_from_ZMX.py tests/test_data/Lazuli_Mark-14_release_17_config1.txt 7 8 15 17 26 27 tests/test_data/UM.yaml --enpp 3 --field_bias 5

    >>> python3 scripts/YAML_from_ZMX.py tests/test_data/Lazuli_Mark-14_17_ESC07_HK02_2_KVG_HChoi08_HK01_conf2.txt 3 7 8 11 15 17 26 27 33 43 45 50 53 54 59 63 67 69 71 72 73 74 79 82 83 89 98 99 104 105 106 107 110 113 tests/test_data/Lazuli_Mark-14_17_ESC07_HK02_2_KVG_HChoi08_HK01_conf2.yaml --enpp 3 --field_bias 5

    Script that creates YAML file from Zemax prescription data TXT file.
    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "prd_file_name",
        type=str,
        help="Path of input file. Only .txt files are supported",
    )
    parser.add_argument(
        "wanted_surf_list",
        nargs="+",  # One or more arguments (required)
        help=(
            "List of surface numbers to be modeled (w/o IMA surface). "
            "Space-separated. Could be list of int or str."
        ),
    )
    parser.add_argument(
        "yaml_file_name",
        type=str,
        help="Name of output file.",
    )
    parser.add_argument(
        "--enpp",
        nargs="*",  # Zero or more arguments (optional)
        default=[],
        help="Optional list of entrance pupil surface numbers. Space-separated list of int or str.",
    )
    parser.add_argument(
        "--field_bias",
        nargs="*",  # Zero or more arguments (optional)
        default=[],
        help="Optional list of field bias surface numbers. Space-separated list of int or str.",
    )

    args = parser.parse_args()

    logger.info(f"{args = }")

    supported_types = ["txt"]
    file_ext = Path(args.prd_file_name).suffix.lower().lstrip(".")
    if file_ext not in supported_types:
        raise OSError(f"File type of {file_ext} is not supported. Must be one of: {supported_types}.")

    if isinstance(args.yaml_file_name, str | Path):
        yaml_file_name = str(args.yaml_file_name)
    else:
        raise OSError(f"File name {args.yaml_file_name} is not supported.")

    wanted_surf_list = parse_intable_list(args.wanted_surf_list)
    enpp = parse_intable_list(args.enpp)
    field_bias = parse_intable_list(args.field_bias)

    logger.debug(f"Processing file: {args.prd_file_name}")

    ZMX2YAML(
        prd_file_name=args.prd_file_name, wanted_surf_list=wanted_surf_list, enpp=enpp, field_bias=field_bias
    ).write_yaml(yaml_file_name)

    logger.info(f"File created: {yaml_file_name}")


def parse_intable_list(values):
    """
    Convert a list of values to a list of integers.

    This function attempts to convert each element in the input list to an integer.
    If any value cannot be converted, a ValueError is raised.

    Parameters
    ----------
    values : list of str or int
        List of values to be converted to integers.

    Returns
    -------
    list of int
        List of integers converted from the input values.

    Raises
    ------
    ValueError
        If any value in the list cannot be converted to an integer.
    """
    result = []
    for v in values:
        try:
            result.append(int(v))
        except ValueError as err:
            raise ValueError(f"Value '{v}' is not an integer or a string representing an integer.") from err
    return result


if __name__ == "__main__":
    main()
