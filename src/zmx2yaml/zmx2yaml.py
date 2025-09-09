"""
ZMX to YAML Conversion Module

This module converts Zemax prescription files to YAML format
suitable for use with Batoid optics simulations.

Author: Pierre Raphaël Nicolas
Date: 05/30/2025
"""

from __future__ import annotations

import logging
import os
import sys
from typing import TextIO

logger = logging.getLogger(__name__)
formatter = logging.Formatter("%(asctime)s - %(name)s - L%(lineno)s - %(levelname)s - %(message)s")
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.setLevel("INFO")

import numpy as np
import yaml

from zmx2yaml.zmx_parsers import PrescriptionDataParser, SurfacePRD

from .anchored_yaml import _ID_AND_NODE, _MEDIA, _NAME_AND_NODE, AnchorDumper, AnchoredValue
from .glass_database import *
from .local_types import _BATOID_AVAILABLE, ConstMedium, SellmeierMedium

# Global medium for air
if _BATOID_AVAILABLE:
    import batoid

    # AIR = AnchoredValue(batoid.Air(pressure=101.325, temperature=293.15, h2o_pressure=2.33), "AIR")
    AIR = AnchoredValue(batoid.vacuum, "AIR")  # Use batoid's vacuum medium
else:
    AIR = AnchoredValue(ConstMedium(1.0), "AIR")


class ZMX2YAML:
    """
    Convert Zemax prescriptions into Batoid optics and export them to YAML.

    This class parses a Zemax file using a custom parser, selects specific surfaces,
    applies field bias and entrance pupil settings, and exports the resulting Batoid
    Optic as a YAML dictionary. It also ensures all media are properly anchored in
    the YAML output for reuse.

    Parameters
    ----------
    prd_file_name : str
        Path to the Zemax prescription (.ZMX) file.
    wanted_surf_list : list of str or int
        List of surface names or indices to extract from the prescription.
    enpp : list of str or int, optional
        Surface(s) used to define the entrance pupil. Defaults to the first in wanted_surf_list.
    field_bias : list of float, optional
        Field bias to apply when generating the optical system.
    """

    _sellmeier_cache = {}

    def __init__(self, prd_file_name=None, wanted_surf_list=None, enpp=None, field_bias=None):
        """
        Initialize the converter with a Zemax file and conversion settings.

        Parameters
        ----------
        prd_file_name : str, optional
            Path to the Zemax ZMX prescription file.
        wanted_surf_list : list of str or int
            Surface names or indices to include in the output.
        enpp : list of str or int, optional
            Surfaces representing the entrance pupil.
        field_bias : list of float, optional
            Field bias values to apply to the parsed prescription.
        Raises
        ------
        Exception
            If prd_file_name or wanted_surf_list is missing.
        """
        if prd_file_name is None:
            raise Exception("No Prescription data file given.")
        else:
            self.prd_file_name = prd_file_name
            self.prd_file = PrescriptionDataParser(prd_file_name)

        if wanted_surf_list is None:
            raise Exception("No surface given.")
        else:
            self.wanted_surf_list = [str(x) if isinstance(x, int) else x for x in wanted_surf_list]

        if enpp is None:
            self.enpp = self.wanted_surf_list[0]
        else:
            self.enpp = [str(x) if isinstance(x, int) else x for x in enpp]

        if field_bias is not None:
            self.field_bias = [str(x) if isinstance(x, int) else x for x in field_bias]

        self.conv_coef = 1000 if "Millimeters" in self.prd_file.unit else (1)  # Conversion to meters if not
        # Medium cache: {(medium_tuple, anchor_name): AnchoredValue}
        self._medium_cache = {}

    def extract_asphere_coefs(self, surface: SurfacePRD) -> list:
        """
        Extract aspheric surface coefficients from a prescription surface and convert them.

        Parameters
        ----------
        surface : SurfacePRD
            The surface object containing asphere parameters.

        Returns
        -------
        list
            List of converted aspheric coefficients.
        """
        converted_params_corrected = [0.0] * 8  # r^2, r^4, r^6, r^8, r^10, r^12, r^14, r^16
        for key, value in surface.items():
            if key.startswith("PARM"):
                index = int(key[4:])  # PARM1 -> index 1, PARM2 -> index 2, etc.
                if index > 8:
                    break  # Stop after PARM8
                exponent = np.log10(self.conv_coef) * (2 * index - 1)  # Compute the conversion exponent
                converted_value = value * (10**exponent)  # Apply conversion
                converted_params_corrected[index - 1] = float(converted_value)
        return converted_params_corrected

    def extract_zernike_coefs(self, surface: SurfacePRD) -> list:
        """
        Extract Zernike polynomial coefficients from a prescription surface.

        Parameters
        ----------
        surface : SurfacePRD
            Surface containing Zernike data fields (e.g., XDAT3, XDAT4...).

        Returns
        -------
        list
            List of Zernike coefficients.
        """
        n_zernike = int(getattr(surface, "XDAT1", 0))
        znk = [0] * n_zernike
        for key, value in surface.items():
            if key.startswith("XDAT") and key not in ("XDAT1", "XDAT2"):
                index = int(key[4:]) - 3  # XDAT3 -> index 0, XDAT4 -> index 1, etc.
                znk[index] = value
        return znk

    @staticmethod
    def medium(n_or_coefs: float | list | tuple) -> ConstMedium | SellmeierMedium:
        """
        Create a constant-index or Sellmeier medium for use in an optical model.

        Parameters
        ----------
        n_or_coefs : float or list/tuple
            If float, returns ConstMedium(n). If list/tuple of 6, returns SellmeierMedium(*coefs).

        Returns
        -------
        object
            Batoid medium with constant index or Sellmeier coefficients.
        """
        if isinstance(n_or_coefs, (list, tuple)) and len(n_or_coefs) == 6:  # noqa: UP038
            return SellmeierMedium(n_or_coefs)  # type: ignore
        return ConstMedium(n_or_coefs)  # type: ignore

    @staticmethod
    def insert_swapped_mediums(a: dict, b: dict) -> dict:
        """
        Replace all mediums in optic `a` by those from optic `b` with matching anchors.

        Parameters
        ----------
        a : dict
            Target optic where mediums will be replaced.
        b : dict
            Source optic providing the AnchoredValue-wrapped mediums.

        Returns
        -------
        dict
            New optic object with swapped mediums.
        """
        new_b = {}
        for key in a:
            if key == "inMedium":
                new_b[key] = a["outMedium"]  # swap!
            elif key == "outMedium":
                new_b[key] = a["inMedium"]  # swap!
            elif key in b:
                new_b[key] = b[key]
        # Add any other fields from b that aren’t in a (fallback)
        for key in b:
            if key not in new_b:
                new_b[key] = b[key]
        return new_b

    def build_dict_surf(self, surf_name: int | str) -> dict:
        """
        Build a surface dictionary for a specific optical surface.

        Parameters
        ----------
        surf_name : int or str
            Index or name of the surface.

        Returns
        -------
        dict
            Dictionary describing the surface parameters.

        Raises
        ------
        ValueError
            If the surface type is not handled.
        """
        surf_name = str(surf_name) if isinstance(surf_name, int) else (surf_name)
        surface = self.prd_file.surface(surf_name)
        conv_coef = self.conv_coef

        curv = surface.CURV
        r = np.inf if not np.any(curv) else 1.0 / (curv * conv_coef)

        # Plane case
        if np.inf == r:
            return {"type": "Plane"}

        conic = getattr(surface, "CONI", 0.0)

        if surface.TYPE == "STANDARD":
                shape_type = "Paraboloid" if conic == -1 else "Quadric"
                if shape_type == "Paraboloid":
                    return {"type": shape_type, "R": r}
                else:
                    return {"type": shape_type, "R": r, "conic": conic}
        elif surface.TYPE == "EVENASPH":
            coefs = self.extract_asphere_coefs(surface)
            return {"type": "Asphere", "imin": 1, "R": r, "conic": conic, "coefs": coefs}
        elif surface.TYPE == "BICONICX":
            conic_y = conic
            conic_x = getattr(surface, "PARM2", 0.0)
            rx = getattr(surface, "PARM1", 0.0) / conv_coef
            return {"type": "Biconic", "Ry": r, "Rx": rx, "ky": conic_y, "kx": conic_x}
        elif surface.TYPE == "SZERNSAG":
            norm_rad = getattr(surface, "XDAT2", 0.0) / self.conv_coef
            znk_coefs = self.extract_zernike_coefs(surface)
            asph_coefs = self.extract_asphere_coefs(surface)
            surfaces = [
                {"type": "Asphere", "imin": 1, "R": r, "conic": conic, "coefs": asph_coefs},
                {"type": "Zernike", "coef": znk_coefs, "R_outer": norm_rad, "R_inner": 0.0},
            ]
            return {"type": "Sum", "items": surfaces}

        raise ValueError(f"Surface type {surface.TYPE} not handled")

    def build_dict_obsc(self, surf_name: int | str) -> dict:
        """
        Build an obscuration dictionary for a given surface.

        Parameters
        ----------
        surf_name : int or str
            Name or index of the obscured surface.

        Returns
        -------
        dict
            Obscuration information dictionary.
        """
        surf_name = str(surf_name) if isinstance(surf_name, int) else (surf_name)
        conv_coef = self.conv_coef
        surface = self.prd_file.surface(surf_name)

        obdc = getattr(surface, "OBDC", None)

        decents = list(map(float, obdc / conv_coef)) if obdc is not None else [0.0, 0.0]
        is_ap = getattr(surface, "ISAP", 1)

        shape_defs = {
            "CLAP": ("Annulus", ["inner", "outer"]),
            "ELAP": ("Ellipse", ["semi_major", "semi_minor"]),
            "SQAP": ("Rectangle", ["width", "height"]),
        }

        for attr, (shape_type, keys) in shape_defs.items():
            data = getattr(surface, attr, None)
            if data is not None:
                dims = list(map(float, data / conv_coef))
                return {
                    "type": "Clear" + shape_type if bool(is_ap) else ("Obsc" + shape_type),
                    "x": decents[0],
                    "y": decents[1],
                    **dict(zip(keys, dims, strict=False)),
                }

        return {"type": "ClearCircle", "x": decents[0], "y": decents[1], "radius": surface.DIAM / 2 / conv_coef}

    def build_dict_crds(self, surf_name: int | str) -> dict:
        """
        Build a coordinate system dictionary for a given surface.

        Parameters
        ----------
        surf_name : int or str
            Surface identifier to extract the coordinate break from.

        Returns
        -------
        dict
            Dictionary with coordinate system changes.
        """
        surf_name = str(surf_name) if isinstance(surf_name, int) else self.prd_file.get_surface_num(surf_name)
        conv_coef = self.conv_coef

        coords = self.prd_file.coordinates(surf_name)
        if coords is not None:
            rot_center = list(map(float, coords.offset / conv_coef))
            angles = list(map(float, np.deg2rad(coords.tilt)))
        else:
            rot_center = [0.0, 0.0, 0.0]
            angles = [0.0, 0.0, 0.0]
        return {
            "x": rot_center[0],
            "y": rot_center[1],
            "z": rot_center[2],
            "rotX": angles[0],
            "rotY": angles[1],
            "rotZ": angles[2],
        }

    @staticmethod
    def find_sellmeier_coefs(glas: str, glass_catalogs: list[str]) -> list:
        """
        Find Sellmeier coefficients for a given glass type from Zemax AGF catalog files.

        This function searches through the provided list of glass catalog names and looks for
        the specified glass name. When found, it extracts the Sellmeier coefficients from the
        corresponding "CD" line and returns them in the order [B1, B2, B3, C1, C2, C3].
        Results are cached for efficiency.

        Parameters
        ----------
        glas : str
            The name of the glass to search for.
        glass_catalogs : list[str]
            List of glass catalog base names (without ".AGF" extension).

        Returns
        -------
        list
            List of Sellmeier coefficients [B1, B2, B3, C1, C2, C3].

        Raises
        ------
        ValueError
            If the glass type is not found in any of the provided AGF files.
        """
        # Check if the glass is already cached
        if glas in ZMX2YAML._sellmeier_cache:
            return ZMX2YAML._sellmeier_cache[glas]

        # Determine the AGF file to use based on the glass name
        agf_file = None
        found_catalog = None
        for cat in glass_catalogs:
            cat_upper = cat.upper()
            catalog_dict = globals().get(cat_upper)
            if catalog_dict and glas in catalog_dict:
                agf_file = os.path.join(
                    os.path.dirname(__file__), "AGF_files", catalog_dict[glas]
                )
                found_catalog = cat_upper
                break
        if agf_file is None:
            raise ValueError(f"Glass {glas} not found in {' or '.join(glass_catalogs)}")

        # Delete unused catalog dicts from globals to free memory
        # for cat in glass_catalogs:
        #     cat_upper = cat.upper()
        #     if cat_upper != found_catalog and cat_upper in globals():
        #         del globals()[cat_upper]

        # Parse the AGF file to find Sellmeier coefficients
        with open(agf_file, "r") as file:
            lines = file.readlines()
            _glas_found = False
            sellmeier_coefs = None
            for line in lines:
                line = line.strip()
                parts = line.split()
                if _glas_found and parts[0] == "CD":
                    coefs = [float(x) for x in parts[1:7]]
                    sellmeier_coefs = [coefs[0], coefs[2], coefs[4], coefs[1], coefs[3], coefs[5]]
                    logger.debug(f"Found medium {glas} in {agf_file}")
                    ZMX2YAML._sellmeier_cache[glas] = sellmeier_coefs
                    return sellmeier_coefs
                if len(parts) > 1 and glas == parts[1]:
                    _glas_found = True
                    continue
        raise ValueError(f"Glass {glas} not found in {found_catalog or 'specified catalogs'}")

    def build_dict_optc(self, surf_name: int | str) -> dict:
        """
        Build an optical surface dictionary for a lens or mirror.

        Parameters
        ----------
        surf_name : int or str
            Index or name of the optical surface.

        Returns
        -------
        dict
            Dictionary representing a Batoid optical surface.
        """
        surf_name = str(surf_name) if isinstance(surf_name, int) else (surf_name)
        surface = self.prd_file.surface(surf_name)

        glas = getattr(surface, "GLAS", None)  # returns None if does not exist
        is_mirror = isinstance(glas, str) and glas.startswith("MIRROR")
        is_refact = isinstance(glas, str) and glas is not None and not glas.startswith("MIRROR")

        if is_refact and glas is not None:
            glas_parts = glas.split()
            sellmeier_coefs = self.find_sellmeier_coefs(glas_parts[0], self.prd_file.glass_catalogs)
            logger.debug(f"Creating medium for glas={glas_parts[0]} with coefs={sellmeier_coefs}")
            # Use a tuple for coefs to make it hashable
            cache_key = (tuple(sellmeier_coefs), str(glas_parts[0]))
            if cache_key not in self._medium_cache:
                self._medium_cache[cache_key] = AnchoredValue(self.medium(sellmeier_coefs), str(glas_parts[0]))
            medium = self._medium_cache[cache_key]
            logger.debug(f"medium type={type(medium.value)} anchor={medium.anchor_name} value={medium.value}")
        else:
            medium = AIR
            logger.debug(
                f"Using AIR medium type={type(medium.value)} anchor={medium.anchor_name} value={medium.value}"
            )

        return {
            "type": "Mirror" if is_mirror else ("RefractiveInterface"),
            "name": getattr(surface, "COMM", surf_name),
            **({"inMedium": AIR, "outMedium": medium} if is_refact else {}),
            "surface": self.build_dict_surf(surf_name),
            "obscuration": self.build_dict_obsc(surf_name),
            "coordSys": self.build_dict_crds(surf_name),
        }

    def build_dict_stop(self) -> dict:
        """
        Build the dictionary representation of the system STOP surface.

        Returns
        -------
        dict
            Dictionary of STOP surface parameters.
        """
        return {
            "type": "Interface",
            "name": "enpp",
            "surface": {"type": "Plane"},
            "coordSys": self.build_dict_crds(self.enpp[0]),
        }

    def build_dict_dctr(self) -> dict:
        """
        Build the dictionary for the detector surface.

        Returns
        -------
        dict
            Dictionary with detector surface properties.
        """
        last_key = next(reversed(self.prd_file.surfaces))
        surf_name = self.prd_file.surfaces[last_key].name[0]
        surface = self.prd_file.surface(surf_name)

        return {
            "type": "Detector",
            "name": getattr(surface, "COMM", surf_name),
            "surface": self.build_dict_surf(surf_name),
            "obscuration": self.build_dict_obsc(surf_name),
            "coordSys": self.build_dict_crds(surf_name),
        }

    def build_dict_meta(self) -> dict:
        """
        Generate metadata for the entire optical system.

        Returns
        -------
        dict
            Dictionary containing system-level metadata (e.g., title, author).
        """
        wavelengths = sorted(self.prd_file.waves or [])

        return {
            "metaData": {
                "file": self.prd_file.filename,
                **(
                    {"glassCatalogs": self.prd_file.glass_catalogs}
                    if getattr(self.prd_file, "glass_catalogs", None) is not None
                    else {}
                ),
                **(
                    {"margin": self.prd_file.clear_semi_diam_margin}
                    if getattr(self.prd_file, "clear_semi_diam_margin", None) is not None
                    else {}
                ),
                **(
                    {"fieldBias": self.prd_file.surface(self.field_bias[0]).PARM3}
                    if hasattr(self, "field_bias")
                    else {}
                ),
                "exitPupilSize": self.prd_file.exit_pupil_diameter / self.conv_coef,
                "wavelengths": wavelengths,
                "fields": self.prd_file.fields,
                **(
                    {"Configurations": self.prd_file.configurations}
                    if self.prd_file.configurations is not None
                    else {}
                ),
            }
        }

    def build_dict_opsy(self) -> dict:
        """
        Build the top-level optical system dictionary.

        Returns
        -------
        dict
            The full Batoid optical system dictionary with nested elements.
        """
        conv_coef = self.conv_coef
        items = [self.build_dict_optc(surf) for surf in self.wanted_surf_list]

        has_glas = lambda surface: getattr(surface, "GLAS", None)
        is_refract = lambda glas: isinstance(glas, str) and glas is not None and not glas.startswith("MIRROR")
        surfaces = [self.prd_file.surface(surf) for surf in self.wanted_surf_list]
        are_refract = [is_refract(has_glas(surface)) for surface in surfaces]

        for i, (a, b) in enumerate(zip(items, items[1:], strict=False)):
            if a["type"] == "RefractiveInterface" and b["type"] == "RefractiveInterface":
                if are_refract[i] and not are_refract[i + 1]:
                    b["obscuration"] = a["obscuration"]
                    items[i + 1] = self.insert_swapped_mediums(a, b)  # Reassign updated b
        items.append(self.build_dict_dctr())

        return {
            "opticalSystem": {
                "type": "CompoundOptic",
                "inMedium": AIR,
                "outMedium": AIR,
                "medium": AIR,
                "backDist": self.prd_file.entrance_pupil_position / conv_coef,
                "sphereRadius": self.prd_file.exit_pupil_position / conv_coef,
                "pupilSize": self.prd_file.entrance_pupil_diameter / conv_coef,
                # 'pupilObscuration': 0.0,
                "stopSurface": self.build_dict_stop(),
                "items": items,
            }
        }

    def build_dict_media(self) -> dict:
        """
        Collect all unique media AnchoredValue objects from the _MEDIA dict.

        .. important::
            "build_dict_opsy" should be called first to populate _MEDIA.

        .. danger::
            Should NOT be used because anchors are not natively given in
            "opticalSystem" by Batoid

        Returns
        -------
        dict
            Dictionary of all media with anchor names as keys.
        """
        media = {anchor_name: av for anchor_name, av in _MEDIA.items()}
        return {"media": media}

    def build_dict_file(self) -> dict:
        """
        Compile all optical system components and metadata into one dictionary.

        Returns
        -------
        dict
            Full optical system definition ready to be serialized.
        """
        return self.build_dict_opsy() | self.build_dict_meta()

    @staticmethod
    def anchor_correction(f: TextIO) -> None:
        """
        Post-process a YAML file to replace auto-generated anchor IDs with human-readable anchor names.

        This function reads the YAML file, replaces all occurrences of &idNNN and *idNNN
        (auto-generated YAML anchors and references) with the corresponding anchor names.

        Parameters
        ----------
        f : TextIO
            An open file object for the YAML file, opened in read/write mode.
        """
        id_to_name = {}
        for id_key, node in _ID_AND_NODE.items():
            id_to_name[id_key] = []
            for name_key, name_node in _NAME_AND_NODE.items():
                if node == name_node:
                    id_to_name[id_key].append(name_key)
        # Clear the global dictionaries
        print('NAME and NODE', _NAME_AND_NODE.keys())
        print()
        print('ID and NODE', _ID_AND_NODE.keys())
        _NAME_AND_NODE.clear()
        _ID_AND_NODE.clear()
        _MEDIA.clear()

        # Post-process YAML file to replace &idNNN and *idNNN with anchor names
        f.seek(0)  # Back to the start of the file
        yaml_str = f.read()
        for id_key, name_keys in id_to_name.items():
            for name_key in name_keys:
                yaml_str = yaml_str.replace(f"&{id_key}", f"&{name_key}")
                yaml_str = yaml_str.replace(f"*{id_key}", f"*{name_key}")
        f.seek(0)  # Back to the start of the file
        f.write(yaml_str)
        f.truncate()  # End of file truncation to remove old content (not necessary)

    def write_yaml(self, name: str) -> None:
        """
        Write the current optical system dictionary to a YAML file.

        Parameters
        ----------
        name : str
            File name or path to write the YAML output to.

        Returns
        -------
        None
        """
        with open(name, "w+", encoding="utf-8") as f:
            yaml.dump(
                self.build_dict_file(),
                f,
                Dumper=AnchorDumper,
                sort_keys=False,  # Keep field order if possible
                default_flow_style=False,  # Force expanded block style
                indent=2,  # 2 spaces
                width=80,  # Wrap lines sensibly
                allow_unicode=True,  # In case non-ASCII names show up
            )

            self.anchor_correction(f)
