import pathlib

import pytest

from zmx2batoid.zmx_parsers_old import PrescriptionDataParser, ZemaxFileParser

TEST_SUPPORT_DATA_DIR = pathlib.Path(__file__).parents[1].joinpath("test_data")

TEST_FILE_ZMX = TEST_SUPPORT_DATA_DIR.joinpath("Ultramarine_Mark-11_DKim1_Release_HChoi02.zmx")
TEST_FILE_PRD = TEST_SUPPORT_DATA_DIR.joinpath(
    "Ultramarine_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt"
)


def test_ZemaxFileParser():
    telescope = ZemaxFileParser(TEST_FILE_ZMX, encoding="utf-8")

    assert telescope.surfaces["7"].COMM == "3000mm CA dia. M1"
    assert telescope.surfaces["9"].COMM == "380X220mm CA M3"

    answer = [190 * 2, 110 * 2]
    for i, a in enumerate(answer):
        assert telescope.surfaces["9"].SQAP[i] == a  # multiplied by 2 manually FIXME: WHY???

    assert pytest.approx(3000.0) == telescope.system_details.ENPD


def test_PrescriptionDataParser():
    prescription = PrescriptionDataParser(TEST_FILE_PRD)

    # FIXME: If the wrong file is given, it finds nothing. Should probably throw warnings?

    assert prescription.entrance_pupil_diameter == pytest.approx(3000.0)
