import os

import numpy as np
import yaml

PATH = os.path.dirname(__file__)

from zmx2batoid.zmx_parsers import PrescriptionDataParser, ZemaxFileParser


class AnchoredValue:
    def __init__(self, value, anchor_name):
        self.value = value
        self.anchor_name = anchor_name


class AnchorDumper(yaml.SafeDumper):
    pass


def represent_anchored_value(dumper, data):
    node = dumper.represent_scalar("tag:yaml.org,2002:float", str(data.value))
    node.anchor = data.anchor_name
    return node


AnchorDumper.add_multi_representer(AnchoredValue, represent_anchored_value)


def ignore_aliases(_, data):
    return not isinstance(data, AnchoredValue)


yaml.representer.SafeRepresenter.ignore_aliases = ignore_aliases


class ZMX2YAML:
    def __init__(self, ZMX_FILE_NAME=None, PRD_FILE_NAME=None, WANTED_SURF_LIST=[], ENPP=[], FIELD_BIAS=[]):
        if ZMX_FILE_NAME is None:
            raise Exception("No ZMX file given.")
        else:
            self.ZMX_FILE_NAME = ZMX_FILE_NAME
            self.ZMX_FILE = ZemaxFileParser(ZMX_FILE_NAME, encoding="utf-8")
        if PRD_FILE_NAME is None:
            raise Exception("No Prescription data file given.")
        else:
            self.PRD_FILE_NAME = PRD_FILE_NAME
            self.PRD_FILE = PrescriptionDataParser(PRD_FILE_NAME)
        if not WANTED_SURF_LIST:
            raise Exception("No surface given.")
        else:
            self.WANTED_SURF_LIST = [str(x) if isinstance(x, int) else x for x in WANTED_SURF_LIST]
        if not ENPP:
            self.ENPP = self.WANTED_SURF_LIST[0]
        else:
            self.ENPP = [str(x) if isinstance(x, int) else x for x in ENPP]
        if FIELD_BIAS:
            self.FIELD_BIAS = [str(x) if isinstance(x, int) else x for x in FIELD_BIAS]

        self.system_details = self.ZMX_FILE.system_details
        self.conv_coef = (
            1000 if self.system_details.UNIT[0].lower() == "mm" else 1
        )  # Conversion to meters if not

    def extract_asphere_coefs(self, surface: ZemaxFileParser.surface) -> list:
        converted_params_corrected = []
        for key, value in surface.items():
            if key.startswith("PARM"):
                index = int(key[4:])  # Extract the index (n)
                exponent = np.log10(self.conv_coef) * (2 * index - 1)  # Compute the conversion exponent
                converted_value = value * (10**exponent)  # Apply conversion
                converted_params_corrected.append(converted_value)
        return converted_params_corrected

    def build_dict_surf(self, SURF_name: int | str) -> dict:
        SURF_name = str(SURF_name) if isinstance(SURF_name, int) else (SURF_name)
        surface = self.ZMX_FILE.surface(SURF_name)
        conv_coef = self.conv_coef

        curv = surface.CURV
        R = np.inf if not np.any(curv) else 1.0 / (curv * conv_coef)

        # Plane case
        if np.inf == R:
            return {"type": "Plane"}

        conic = getattr(surface, "CONI", 0.0)

        if surface.TYPE == "STANDARD":
            shape_type = "Paraboloid" if conic == -1 else "Quadric"
            return {"type": shape_type, "R": R, "conic": conic}
        elif surface.TYPE == "EVENASPH":
            coefs = self._extract_asphere_coefs(surface)
            return {"type": "Asphere", "R": R, "conic": conic, "coefs": coefs}
        elif surface.TYPE == "BICONICX":
            conicY = conic
            conicX = getattr(surface, "PARM2", 0.0)
            Rx = getattr(surface, "PARM1", 0.0) / conv_coef
            return {"type": "Biconic", "Ry": R, "Rx": Rx, "conicy": conicY, "conicx": conicX}

    def build_dict_obsc(self, SURF_name: int | str) -> dict:
        SURF_name = str(SURF_name) if isinstance(SURF_name, int) else (SURF_name)
        conv_coef = self.conv_coef
        surface = self.ZMX_FILE.surface(SURF_name)

        obdc = getattr(surface, "OBDC", None)
        decents = list(map(float, obdc / conv_coef)) if obdc is not None else [0.0, 0.0]

        shape_defs = {
            "CLAP": ("ClearAnnulus", ["inner", "outer"]),
            "ELAP": ("ClearEllipse", ["semi_major", "semi_minor"]),
            "SQAP": ("ClearRectangle", ["width", "height"]),
        }

        for attr, (shape_type, keys) in shape_defs.items():
            data = getattr(surface, attr, None)
            if data is not None:
                dims = list(map(float, data / conv_coef))
                return {
                    "type": shape_type,
                    "x": decents[0],
                    "y": decents[1],
                    **dict(zip(keys, dims, strict=False)),
                }

        return {"type": "ClearCircle", "x": decents[0], "y": decents[1], "radius": surface.DIAM / conv_coef}

    def build_dict_crds(self, SURF_name: int | str) -> dict:
        SURF_name = str(SURF_name) if isinstance(SURF_name, int) else (SURF_name)
        conv_coef = self.conv_coef

        rotCenter = list(map(float, self.PRD_FILE.surface(SURF_name).offset / conv_coef))
        angles = list(map(float, np.deg2rad(self.PRD_FILE.surface(SURF_name).tilt)))
        return {
            "x": rotCenter[0],
            "y": rotCenter[1],
            "z": rotCenter[2],
            "rotX": angles[0],
            "rotY": angles[1],
            "rotZ": angles[2],
        }

    def build_dict_optc(self, SURF_name: int | str) -> dict:
        SURF_name = str(SURF_name) if isinstance(SURF_name, int) else (SURF_name)
        surface = self.ZMX_FILE.surface(SURF_name)

        glas = getattr(surface, "GLAS", "")  # returns empty str in does not exist
        is_mirror = isinstance(glas, str) and glas.startswith("MIRROR")

        return {
            "type": "Mirror" if is_mirror else "Interface",
            "name": surface.COMM,
            "surface": self.build_dict_surf(SURF_name),
            "obscuration": self.build_dict_obsc(SURF_name),
            "coordSys": self.build_dict_crds(SURF_name),
        }

    def build_dict_stop(self) -> dict:
        return {
            "type": "Interface",
            "name": "ENPP",
            "surface": {"type": "Plane"},
            "coordSys": self.build_dict_crds(self.ENPP[0]),
        }

    def build_dict_dctr(self) -> dict:
        last_key = next(reversed(self.ZMX_FILE.surfaces))
        SURF_name = self.ZMX_FILE.surfaces[last_key].name
        surface = self.ZMX_FILE.surface(SURF_name)
        return {
            "type": "Detector",
            "name": surface.COMM,
            "surface": self.build_dict_surf(SURF_name),
            "obscuration": self.build_dict_obsc(SURF_name),
            "coordSys": self.build_dict_crds(SURF_name),
        }

    def build_dict_opsy(self) -> dict:
        conv_coef = self.conv_coef
        items = [self.build_dict_optc(surf) for surf in self.WANTED_SURF_LIST]
        items.append(self.build_dict_dctr())
        air_medium = AnchoredValue(1.0, "air")
        wavelengths = sorted({round(float(wav.split()[1]) * 1e-6, 10) for wav in self.system_details.WAVM})
        return {
            "opticalSystem": {
                "type": "CompoundOptic",
                "name": "",  # NAME,  #FIXME: why was this the name of the file?
                "inMedium": air_medium,
                "outMedium": air_medium,
                "medium": air_medium,
                "backDist": self.PRD_FILE.entrance_pupil_position / conv_coef,
                "sphereRadius": self.PRD_FILE.exit_pupil_position / conv_coef,
                "pupilSize": self.PRD_FILE.entrance_pupil_diameter / conv_coef,
                # 'pupilObscuration': 0.0,
                "stopSurface": self.build_dict_stop(),
                "items": items,
            },
            "metaData": {
                "fieldBias": self.ZMX_FILE.surface(self.FIELD_BIAS[0]).PARM3 if self.FIELD_BIAS else None,
                "exitPupilSize": self.PRD_FILE.exit_pupil_diameter / self.conv_coef,
                "wavelengths": wavelengths,
                "fields": self.system_details.FLDS,
            },
        }

    def write_yaml(self, output_file) -> None:
        with open(output_file, "w") as f:
            yaml.dump(
                self.build_dict_opsy(),
                f,
                Dumper=AnchorDumper,
                sort_keys=False,  # Keep field order if possible
                default_flow_style=False,  # Force expanded block style
                indent=2,  # 2 spaces like your file
                width=80,  # Wrap lines sensibly
                allow_unicode=True,  # In case non-ASCII names show up
            )


# Should go in docs
# if __name__ == "__main__":
#     _PATH = "/Users/pierrenicolas/Documents/UASAL/stp_batoid/Batoid4LOFT/support_data/Lazuli/STOP/"
#     _ZMX_FILE_NAME = _PATH + "Lazuli_Mark-11_DKim1_Release_HChoi02.zmx"
#     _PRD_FILE_NAME = _PATH + "Lazuli_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt"

#     ZMX2YAML(
#         ZMX_FILE_NAME=_ZMX_FILE_NAME,
#         PRD_FILE_NAME=_PRD_FILE_NAME,
#         WANTED_SURF_LIST=[7, 8, 9, 11],
#         ENPP=[3],
#         FIELD_BIAS=[5],
#     ).write_yaml("LAZULI STOP")
