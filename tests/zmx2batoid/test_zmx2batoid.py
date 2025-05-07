import pathlib

import pytest
import yaml

from zmx2batoid import ZMX2YAML

TEST_SUPPORT_DATA_DIR = pathlib.Path(__file__).parents[1].joinpath("test_data")

TEST_FILE_ZMX = TEST_SUPPORT_DATA_DIR.joinpath("Ultramarine_Mark-11_DKim1_Release_HChoi02.zmx")
TEST_FILE_PRD = TEST_SUPPORT_DATA_DIR.joinpath(
    "Ultramarine_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt"
)


def test_ZMX2YAML():
    output_file = TEST_SUPPORT_DATA_DIR.joinpath("test_output_description.yaml")
    # pull surfaces that correspond to M1, M2, M3, M4.
    ZMX2YAML(
        ZMX_FILE_NAME=TEST_FILE_ZMX,
        PRD_FILE_NAME=TEST_FILE_PRD,
        WANTED_SURF_LIST=[7, 8, 9, 11],
        ENPP=[3],
        FIELD_BIAS=[5],
    ).write_yaml(output_file)

    # Now read in the file and make sure proper values exist.
    # FIXME: Need to verify absolute coordinates here as well

    with open(output_file, "r") as file:
        data = yaml.safe_load(file)

    # values in asserts determined from manual read of prescription and/or zmx file.
    assert data["opticalSystem"]["items"][0]["name"] == "3000mm CA dia. M1"
    assert data["opticalSystem"]["items"][0]["surface"]["conic"] == pytest.approx(-0.99385364904129125)

    # check M3 size
    assert data["opticalSystem"]["items"][2]["name"] == "380X220mm CA M3"
    answer = [190 * 2, 110 * 2]  # from test_zmxparsers
    # But units are now meters? FIXME: Is this correct?
    assert data["opticalSystem"]["items"][2]["obscuration"]["width"] == pytest.approx(answer[0] / 1e3)
    assert data["opticalSystem"]["items"][2]["obscuration"]["height"] == pytest.approx(answer[1] / 1e3)

    # last surface should be the detector (surface 15)
    assert data["opticalSystem"]["items"][4]["name"] == "420 x 180mm Flat Detector"

    # FIXME: I don't understand ENPP and how it's used, this is the STOP? and a keyword for batoid?
