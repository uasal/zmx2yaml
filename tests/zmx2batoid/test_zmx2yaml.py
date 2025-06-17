import pathlib

import pytest
import yaml
import numpy as np

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src'))

from zmx2batoid import ZMX2YAML

TEST_SUPPORT_DATA_DIR = pathlib.Path(__file__).parents[1].joinpath("test_data")

TEST_FILE_PRD = TEST_SUPPORT_DATA_DIR.joinpath(
    "Ultramarine_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt"
)


def test_ZMX2YAML():
    output_file = TEST_SUPPORT_DATA_DIR.joinpath("test_output_description.yaml")
    # pull surfaces that correspond to M1, M2, M3, M4.
    ZMX2YAML(
        prd_file_name    = TEST_FILE_PRD,
        wanted_surf_list = [7, 8, 9, 11],
        enpp             = [3],
        field_bias       = [5]
    ).write_yaml(output_file)

    # Now read in the file and make sure proper values exist.
    # FIXME: Need to verify absolute coordinates here as well

    with open(output_file, "r") as file:
        data = yaml.safe_load(file)

    # check M1
    opt = data["opticalSystem"]["items"][0]
    assert opt["name"] == "3000mm CA dia. M1"
    curv = -1.067098742061318935e-04
    assert opt["surface"]["R"] == pytest.approx(1 / curv / 1e3)
    assert opt["surface"]["conic"] == pytest.approx(-0.99385364904129125)

    # check M2
    opt = data["opticalSystem"]["items"][1]
    assert opt["name"] == "220mm CA dia. M2"
    curv = -1.486343507359631951e-03
    assert opt["surface"]["R"] == pytest.approx(1 / curv / 1e3)
    assert opt["surface"]["conic"] == pytest.approx(-2.7600798790182837)

    # check M3
    opt = data["opticalSystem"]["items"][2]
    assert opt["name"] == "380X220mm CA M3"
    curv = -1.355209620642092421e-03
    assert opt["surface"]["R"] == pytest.approx(1 / curv / 1e3)
    assert opt["surface"]["conic"] == pytest.approx(-0.59645551009734266)
    answer = np.array([190, 110]) * 2 / 1e3
    assert opt["obscuration"]["width"]  == pytest.approx(answer[0])
    assert opt["obscuration"]["height"] == pytest.approx(answer[1])
    assert opt["obscuration"]["y"] == pytest.approx(15 / 1e3)

    # check Flat Detector
    opt = data["opticalSystem"]["items"][4]
    assert opt["name"] == "420 x 180mm Flat Detector"

if __name__=='__main__':
    test_ZMX2YAML()
