"""
Unit tests for the ZMX2YAML conversion functionality.

This module tests the conversion of a Zemax prescription data file to a YAML description
using the ZMX2YAML class.

Tested features:
- Correct parsing and conversion of optical surfaces (M1, M2, M3, M4, Detector)
- Validation of key parameters in the output YAML file
"""
import pathlib
import sys

import numpy as np
import pytest
import yaml

from zmx2batoid import ZMX2YAML

TEST_SUPPORT_DATA_DIR = pathlib.Path(__file__).parents[1].joinpath("test_data")

TEST_FILE_PRD = TEST_SUPPORT_DATA_DIR.joinpath(
    "Ultramarine_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt"
)


def test_zmx2yaml():
    """
    Test the ZMX2YAML conversion from Zemax prescription data to YAML.

    This test checks that the output YAML file contains the correct values for each optical
    surface (M1, M2, M3, M4, Detector).
    It validates the following for each surface:
        - Name
        - Surface radius (R)
        - Conic constant
        - Coordinate system (z, rotX, y)
        - Obscuration parameters (inner, outer, width, height, semi_major, semi_minor, y)
    """
    output_file = TEST_SUPPORT_DATA_DIR.joinpath("test_output_description.yaml")
    # pull surfaces that correspond to M1, M2, M3, M4.
    ZMX2YAML(
        prd_file_name    = TEST_FILE_PRD,
        wanted_surf_list = [7, 8, 9, 11],
        enpp             = [3],
        field_bias       = [5]
    ).write_yaml(output_file)

    # Now read in the file and make sure proper values exist.

    with open(output_file, "r") as file:
        data = yaml.safe_load(file)

    # check M1 requirements
    opt = data["opticalSystem"]["items"][0]
    assert opt["name"] == "3000mm CA dia. M1"
    curv = -1.067098742061318935E-04
    assert opt["surface"]["R"]     == pytest.approx(1 / curv / 1e3)
    assert opt["surface"]["conic"] == pytest.approx(-0.99385364904129125)
    assert opt["coordSys"]["z"] == pytest.approx(0.000000000E+00 / 1e3)
    answer = np.array([0, 1500.1]) / 1e3
    assert opt["obscuration"]["inner"] == pytest.approx(answer[0])
    assert opt["obscuration"]["outer"] == pytest.approx(answer[1])
    assert opt["obscuration"]["y"]     == pytest.approx(1900 / 1e3)

    # check M2 requirements
    opt = data["opticalSystem"]["items"][1]
    assert opt["name"] == "220mm CA dia. M2"
    curv = -1.486343507359631951E-03
    assert opt["surface"]["R"]     == pytest.approx(1 / curv / 1e3)
    assert opt["surface"]["conic"] == pytest.approx(-2.7600798790182837)
    assert opt["coordSys"]["z"] == pytest.approx(-4.440000000E+03 / 1e3)
    answer = np.array([0, 110]) / 1e3
    assert opt["obscuration"]["inner"] == pytest.approx(answer[0])
    assert opt["obscuration"]["outer"] == pytest.approx(answer[1])
    assert opt["obscuration"]["y"]     == pytest.approx(115 / 1e3)

    # check M3 requirements
    opt = data["opticalSystem"]["items"][2]
    assert opt["name"] == "380X220mm CA M3"
    curv = -1.355209620642092421E-03
    assert opt["surface"]["R"]     == pytest.approx(1 / curv / 1e3)
    assert opt["surface"]["conic"] == pytest.approx(-0.59645551009734266)
    assert opt["coordSys"]["z"] == pytest.approx(-3.008751953E+03 / 1e3)
    answer = np.array([190, 110]) * 2 / 1e3
    assert opt["obscuration"]["width"]  == pytest.approx(answer[0])
    assert opt["obscuration"]["height"] == pytest.approx(answer[1])
    assert opt["obscuration"]["y"]      == pytest.approx(15 / 1e3)

    # check M4 requirements
    opt = data["opticalSystem"]["items"][3]
    assert opt["name"] == "110X80mm CA dia. M4 Flat"
    assert opt["coordSys"]["z"]    == pytest.approx(-3.498751953E+03 / 1e3)
    assert opt["coordSys"]["rotX"] == pytest.approx(np.deg2rad(6.000000000E+00))
    answer = np.array([55, 40]) / 1e3
    assert opt["obscuration"]["semi_major"] == pytest.approx(answer[0])
    assert opt["obscuration"]["semi_minor"] == pytest.approx(answer[1])
    assert opt["obscuration"]["y"]          == pytest.approx(-42 / 1e3)

    # check Flat Detector requirements
    opt = data["opticalSystem"]["items"][4]
    assert opt["name"] == "420 x 180mm Flat Detector"
    assert opt["coordSys"]["y"]    == pytest.approx(-1.605042168E+02 / 1e3)
    assert opt["coordSys"]["z"]    == pytest.approx(-2.743638982E+03 / 1e3)
    assert opt["coordSys"]["rotX"] == pytest.approx(np.deg2rad(1.200000000E+01))
    answer = np.array([210, 90]) * 2 / 1e3
    assert opt["obscuration"]["width"]  == pytest.approx(answer[0])
    assert opt["obscuration"]["height"] == pytest.approx(answer[1])
    assert opt["obscuration"]["y"]      == pytest.approx(-120 / 1e3)

if __name__ == '__main__':
    pytest.main([__file__])
