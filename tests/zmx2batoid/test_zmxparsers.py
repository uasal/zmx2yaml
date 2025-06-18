import pathlib

import pytest

from zmx2batoid.zmx_parsers import PrescriptionDataParser

TEST_SUPPORT_DATA_DIR = pathlib.Path(__file__).parents[1].joinpath("test_data")

TEST_FILE_ZMX = TEST_SUPPORT_DATA_DIR.joinpath("Ultramarine_Mark-11_DKim1_Release_HChoi02.zmx")
TEST_FILE_PRD = TEST_SUPPORT_DATA_DIR.joinpath(
    "Ultramarine_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt"
)


def test_PrescriptionDataParser():
    prescription = PrescriptionDataParser(TEST_FILE_PRD)

    # FIXME: If the wrong file is given, it finds nothing. Should probably throw warnings?

    assert prescription.entrance_pupil_diameter == pytest.approx(3000.0)
