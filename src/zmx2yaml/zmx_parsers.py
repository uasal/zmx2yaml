"""
ZMX Prescription Data Parser

This module parses Zemax's prescription files.

Author: Pierre Raphaël Nicolas
Date: 06/18/2025
"""

import os

import numpy as np


class PrescriptionDataParser:
    """Parses optical prescription data files to extract relevant parameters."""

    def __init__(self, file_path):
        self.file_path = file_path

        self.surface_coordinates = {}
        self.extract_matrices()

        # self.entrance_pupil_position = None
        # self.entrance_pupil_diameter = None
        # self.exit_pupil_position = None
        # self.exit_pupil_diameter = None
        self.extract_pupils()

        self.configurations = None
        # self.extract_multi_configurations()

        self.fields = None
        self.extract_fields()

        self.waves = None
        self.extract_waves()

        self.extract_surface()

        self.extract_surface_details()

        self.extract_surface_index()

    def _is_numeric_list(self, lst):
        """Check if all elements in the list can be converted to float."""
        try:
            [float(x) for x in lst]
            return True
        except ValueError:
            return False

    def extract_matrices(self):
        """Extracts rotation matrices, offsets, tilts, and comments from the file."""
        with open(self.file_path, "r") as file:
            lines = file.readlines()

        lines_iter = iter(lines)
        for line in lines_iter:
            stripped_line = line.lstrip().split()  # Handle lines with leading spaces
            if (
                len(stripped_line) >= 6
                and stripped_line[0].isdigit()
                and self._is_numeric_list(stripped_line[1:6])
            ):
                surface_num = stripped_line[0]
                rotation_1 = np.array(stripped_line[1:4], dtype=float)
                offset_1 = float(stripped_line[4])
                tilt_1 = float(stripped_line[5])
                comment = " ".join(stripped_line[6:]) if len(stripped_line) > 6 else ""

                try:
                    line2 = next(lines_iter).strip().split()
                    line3 = next(lines_iter).strip().split()
                except StopIteration:
                    print(f"Warning: Incomplete data for surface {surface_num}.")
                    self.surface_coordinates[surface_num] = SurfaceCoordinates(None, None, None, comment)
                    continue

                if (
                    len(line2) >= 5
                    and len(line3) >= 5
                    and self._is_numeric_list(line2[:5])
                    and self._is_numeric_list(line3[:5])
                ):
                    rotation_2 = np.array(line2[:3], dtype=float)
                    offset_2 = float(line2[3])
                    tilt_2 = float(line2[4])
                    rotation_3 = np.array(line3[:3], dtype=float)
                    offset_3 = float(line3[3])
                    tilt_3 = float(line3[4])

                    rotation_matrix = np.vstack([rotation_1, rotation_2, rotation_3])
                    offset_vector = np.array([offset_1, offset_2, offset_3], dtype=float)
                    tilt_vector = np.array([tilt_1, tilt_2, tilt_3], dtype=float)
                else:
                    rotation_matrix = None
                    offset_vector = None
                    tilt_vector = None

                self.surface_coordinates[surface_num] = SurfaceCoordinates(
                    rotation_matrix, offset_vector, tilt_vector, comment
                )

    def coordinates(self, surface_num):
        """Get SurfaceCoordinates object for a specific surface."""
        surface = self.surface_coordinates.get(str(surface_num), None)
        if surface is None:
            print(f"Warning: Surface {surface_num} not found.")
        return surface

    def extract_pupils(self):
        """Extract entrance and exit pupil positions and sizes from the file without using regex."""
        with open(self.file_path, "r") as file:
            lines = file.readlines()

        for line in lines:
            parts = line.split(":")  # Split at ":" to separate labels from values

            if len(parts) > 1:
                key = parts[0].strip()
                value = parts[1].strip()

                # File name
                if key == "File":  # to ensure it is one 'File'
                    # which is found and not another line finishing by 'File'
                    try:
                        drive = value
                        rest_of_path = parts[2].strip()
                        full_path = f"{drive}:{rest_of_path}"
                        norm_path = full_path.replace("\\", "/")
                        self.filename = os.path.splitext(os.path.basename(norm_path))[0]  # import os
                    except Exception as e:
                        print(f"Warning: Could not extract file name. Error: {e}")

                # Unit
                elif "Lens Units" in key:
                    try:
                        self.unit = value
                    except ValueError:
                        print("Warning: Could not convert Surfaces to integer.")

                # Number of surfaces
                elif "Surfaces" in key:
                    try:
                        self.surface_nb = int(value)
                    except ValueError:
                        print("Warning: Could not convert Surfaces to integer.")

                # Margin
                elif "Clear Semi Diameter Margin %" in key:
                    try:
                        self.clear_semi_diam_margin = float(value)
                    except ValueError:
                        print("Warning: Could not convert Entrance Pupil Position to float.")

                # Entrance Pupil
                elif "Entrance Pupil Position" in key:
                    try:
                        self.entrance_pupil_position = float(value)
                    except ValueError:
                        print("Warning: Could not convert Entrance Pupil Position to float.")

                elif "Entrance Pupil Diameter" in key:
                    try:
                        self.entrance_pupil_diameter = float(value)
                    except ValueError:
                        print("Warning: Could not convert Entrance Pupil Diameter to float.")

                # Exit Pupil
                elif "Exit Pupil Position" in key:
                    try:
                        self.exit_pupil_position = float(value)
                    except ValueError:
                        print("Warning: Could not convert Exit Pupil Position to float.")

                elif "Exit Pupil Diameter" in key:
                    try:
                        self.exit_pupil_diameter = float(value)
                    except ValueError:
                        print("Warning: Could not convert Exit Pupil Diameter to float.")

                elif "Glass Catalogs" in key:
                    try:
                        self.glass_catalogs = value.strip().split()
                    except Exception as e:
                        print(f"Warning: Could not parse Glass Catalog(s). Error: {e}")

    def extract_fields(self):
        """Extract and return field coordinates from the system data."""
        fields = []

        with open(self.file_path, "r") as file:
            lines = file.readlines()

            field_i = 1  # count fields
            offset_i = 1  # count lines to ignore
            field_flag = False  # flag for field's section
            nb_fields = 0  # Ensure nb_fields is always defined
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(":", 1)  # Only split on first ":"
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                if "Fields" in key:
                    field_flag = True
                    nb_fields = int(value)  # total number of fields
                    continue
                if field_flag:
                    if offset_i <= 2:
                        offset_i += 1
                        continue
                    elif field_i <= nb_fields:
                        key_parts = key.split()
                        fields.append([float(key_parts[1]), float(key_parts[2])])
                        field_i += 1
                        continue
                    else:
                        break
        self.fields = fields

    def extract_waves(self):
        """Extract and store the list of wavelength values from the system data."""
        waves = []

        with open(self.file_path, "r") as file:
            lines = file.readlines()

            units = None
            wave_i = 1  # count waves
            offset_i = 1  # count lines to ignore
            waves_flag = False  # flag for wave's section
            nb_waves = 0  # Ensure nb_waves is always defined
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(":", 1)  # Only split on first ":"
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                if key == "Wavelengths":
                    waves_flag = True
                    nb_waves = int(value)  # total number of waves
                    continue
                if waves_flag:
                    if "Units" in key:
                        units = value
                    if offset_i <= 2:
                        offset_i += 1
                        continue
                    elif wave_i <= nb_waves:
                        key_parts = key.split()
                        waves.append(float(key_parts[1]))
                        wave_i += 1
                        continue
                    else:
                        waves = [w * 1e-6 for w in waves] if units == "?m" else (waves)  # '?m' means 'µm'
                        break
        self.waves = waves

    def extract_surface(self):
        """Parse and store surface prescription data from the input file."""

        def is_float(s):
            s = s.strip()
            if s.lstrip("+-").isdigit():
                return True  # it's an integer
            if s.count(".") == 1:
                left, right = s.split(".")
                if left.lstrip("+-").isdigit() and right.isdigit():
                    return True  # it's a float
            return False
        
        def unique_preserve_order(seq):
            seen = set()
            return [x for x in seq if not (x in seen or seen.add(x))]

        surfaces = {}
        surface_i = 0  # count surfaces

        offset_i = 1  # count lines to ignore

        in_data_summary_flag = False  # flag for surface's section

        with open(self.file_path, "r") as file:
            lines = file.readlines()

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(":", 1)  # Only split on first ":"
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                if key.startswith("SURFACE DATA SUMMARY"):
                    in_data_summary_flag = True
                    continue
                if in_data_summary_flag:
                    if offset_i <= 1:
                        offset_i += 1
                        continue
                    # if surface_i <= surface_nb:
                    key_parts = key.split("\t")
                    surf_line = key_parts + [""] if len(key_parts) == 9 else (key_parts)
                    surf_line = [s.replace(" ", "") for s in surf_line[:-1]] + [surf_line[-1].strip()]

                    if surf_line[0] == 'OBJ':
                        surface_i = 0
                    elif surf_line[0] == 'IMA' or surf_line[0] == 'STO':
                        surface_i += 1
                    else:
                        surface_i = int(surf_line[0])

                    name = (
                        [str(surface_i), surf_line[0]]
                        if not surf_line[-1]
                        else [str(surface_i), surf_line[0], surf_line[-1]]
                    )
                    current_surface = SurfacePRD(name=unique_preserve_order(name))
                    
                    current_surface.TYPE = surf_line[1]

                    curv = 1 / float(surf_line[2]) if is_float(surf_line[2]) else (0.0)
                    current_surface.CURV = curv

                    disz = float(surf_line[3]) if is_float(surf_line[3]) else (0.0)
                    current_surface.DISZ = disz

                    glas = surf_line[4]
                    if glas:
                        current_surface.GLAS = surf_line[4]

                    diam = float(surf_line[5]) if is_float(surf_line[5]) else (None)
                    if diam is not None:
                        current_surface.DIAM = diam

                    coni = float(surf_line[-2]) if is_float(surf_line[-2]) else (None)
                    if coni is not None:
                        current_surface.CONI = coni

                    comm = surf_line[-1] + ":" + value if value else (surf_line[-1])
                    if comm:
                        # Check for duplicate COMM values
                        comms = [s.COMM for s in surfaces.values() if hasattr(s, "COMM")]
                        if comm in comms:
                            comm = "(bis) " + comm
                        current_surface.COMM = comm

                    surfaces[str(surface_i)] = current_surface

                    if surf_line[0] == 'IMA':
                        break

        self.surfaces = surfaces

    def extract_surface_details(self):
        """Extract detailed surface data from the prescription file."""
        surface_i = 0  # count surfaces
        surface_nb = self.surface_nb  # total number of surfaces

        offset_i = 1  # count lines to ignore

        in_data_details_flag = False  # flag for surface details' section

        aper_type = None
        is_aper = None
        obdc = [0.0, 0.0]  # aperture decenter
        aper = [0.0, 0.0]  # aperture size
        parm = []  # parameters
        xdat = []  # additional parameters
        surf_type = None

        with open(self.file_path, "r") as file:
            lines = file.readlines()

            for line in lines:
                line = line.strip()

                parts = line.split(":", 1)  # Only split on first ":"
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                if key.startswith("SURFACE DATA DETAIL"):
                    in_data_details_flag = True
                    continue
                if in_data_details_flag:
                    if offset_i <= 1:
                        offset_i += 1
                        continue
                    if not key:  # meaning empty line i.e. end of a surface
                        current_surface = self.surfaces[str(surface_i)]
                        if any(obdc):
                            current_surface.OBDC = np.array(obdc)
                        if aper_type is not None:
                            setattr(current_surface, aper_type, np.array(aper))
                        if is_aper is not None:
                            current_surface.ISAP = int(is_aper)
                        if parm:
                            for j in range(len(parm)):
                                setattr(current_surface, f"PARM{j + 1}", parm[j])
                        if xdat:
                            for j in range(len(xdat)):
                                setattr(current_surface, f"XDAT{j + 1}", xdat[j])

                        aper_type = None
                        is_aper = None
                        obdc = [0.0, 0.0]
                        aper = [0.0, 0.0]
                        parm = []
                        xdat = []
                        surf_type = None

                        continue
                    if surface_i <= surface_nb:
                        if key.startswith("Surface"):
                            key_parts = key.split()
                            if key_parts[1] == 'OBJ':
                                surface_i = 0
                            elif key_parts[1] == 'IMA' or key_parts[1] == 'STO':
                                surface_i += 1
                            else:
                                surface_i = int(key_parts[1])

                            if key_parts[1] in self.surfaces[str(surface_i)].name:
                                surf_type = self.surfaces[str(surface_i)].TYPE
                                continue
                            else:
                                raise Exception("ERROR")
                        else:
                            if key.startswith("Aperture"):
                                ap = value.split()[0]

                                aperture_codes = {
                                    "Elliptical": "ELAP",
                                    "Rectangular": "SQAP",
                                    "Circular": "CLAP",
                                }
                                aper_type = aperture_codes.get(ap)

                                is_aper = value.split()[1].startswith("Aperture")
                                continue

                            if key.startswith("Minimum Radius"):
                                aper[0] = float(value)
                                continue
                            elif key.startswith("Maximum Radius"):
                                aper[1] = float(value)
                                continue
                            elif key.startswith("X Half Width"):
                                aper[0] = float(value) * 2 if aper_type == "SQAP" else (float(value))
                                continue
                            elif key.startswith("Y Half Width"):
                                aper[1] = float(value) * 2 if aper_type == "SQAP" else (float(value))
                                continue

                            if key.startswith("X- Decenter"):
                                obdc[0] = float(value)
                                continue
                            elif key.startswith("Y- Decenter"):
                                obdc[1] = float(value)

                            if surf_type is not None and surf_type == "COORDBRK":
                                if key.startswith("Order"):
                                    parm.append(0 if value == "Decenter then tilt" else (1))
                                else:
                                    parm.append(float(value))
                                continue
                            elif surf_type is not None and surf_type == "EVENASPH":
                                if key.startswith("Coefficient"):
                                    parm.append(float(value))
                                    continue
                            elif surf_type is not None and surf_type == "BICONICX":
                                if key.startswith("X Radius") or key.startswith("X Conic"):
                                    parm.append(float(value))
                                    continue
                            elif surf_type is not None and surf_type == "SZERNSAG":
                                if key.startswith("Coefficient") or key.startswith("Zernike Decenter"):
                                    parm.append(float(value))
                                    continue
                                if (
                                    key.startswith("Number")
                                    or key.startswith("Normalization")
                                    or key.startswith("Zernike Term")
                                ):
                                    xdat.append(float(value))
                                    continue
                    else:
                        break

    def extract_surface_index(self):
        """Extract and assign refractive indexes to the optical surfaces."""
        surface_i = 0  # count surfaces
        surface_nb = self.surface_nb  # total number of surfaces

        offset_i = 1  # count lines to ignore

        in_index_flag = False  # flag for index's section
        has_glas = False
        air_index_ref = 1.0  # Default value in case it's not set in the file

        with open(self.file_path, "r") as file:
            lines = file.readlines()

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(":", 1)  # Only split on first ":"
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                if key.startswith("INDEX OF REFRACTION DATA"):
                    in_index_flag = True
                    continue
                if in_index_flag:
                    if offset_i <= 6:
                        if key.startswith("Absolute air index"):
                            air_index_ref = float(value.split()[0])
                        offset_i += 1
                        continue
                    surface_i = int(key.split("\t")[0])
                    key_parts = key.split("\t")
                    current_surface = self.surfaces[str(surface_i)]
                    if key_parts[0].strip() in current_surface.name:
                        has_glas = hasattr(current_surface, "GLAS")
                    if has_glas and current_surface.GLAS != "MIRROR":
                        # index is referred to air index
                        index = float(key_parts[4].strip()) + (air_index_ref - 1.0)
                        current_surface.GLAS = " ".join([current_surface.GLAS, str(index)])
                        
                    if surface_i == surface_nb:
                        break

    def extract_multi_configurations(self):
        """Extract multiple configuration blocks from the system file."""
        configurations = {}
        current_config = None
        in_configuration = False  # flag for configuration's section

        with open(self.file_path, "r") as file:
            lines = file.readlines()

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(":", 1)  # Only split on first ":"
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                key_parts = key.split()

                # Detect new configuration block
                if len(key_parts) == 2 and key_parts[0] == "Configuration" and key_parts[1].isdigit():
                    current_config = f"Configuration {key_parts[1]}"
                    configurations[current_config] = {}
                    in_configuration = True
                    continue

                # Stop reading if we reach a new section
                if key.startswith("SOLVE AND VARIABLE DATA") or key.startswith("END") or "DATA" in key:
                    in_configuration = False
                    continue

                if in_configuration and current_config:
                    value_parts = value.split()
                    if not value_parts:
                        continue
                    elif key.split()[1] == "Comment":
                        configurations[current_config][key] = value
                    else:
                        configurations[current_config][" ".join(key.split())] = float(value_parts[0])

        self.configurations = configurations

    def get_entrance_pupil_position(self):
        """Get the extracted entrance pupil position."""
        return self.entrance_pupil_position

    def get_entrance_pupil_diameter(self):
        """Get the extracted entrance pupil size."""
        return self.entrance_pupil_diameter

    def get_exit_pupil_position(self):
        """Get the extracted exit pupil position."""
        return self.exit_pupil_position

    def get_exit_pupil_diameter(self):
        """Get the extracted exit pupil diameter."""
        return self.exit_pupil_diameter

    def surface(self, surface_name):
        """
        Retrieve a Surface object by its surface number, COMM name, or tuple key.
        """
        for surface in self.surfaces.values():
            if surface_name in surface.name:
                return surface
        raise Exception(f"{surface_name} is not among available surfaces")

    def get_surface_num(self, surface_name):
        """Return the surface number matching the given name."""
        for surface in self.surfaces.values():
            if surface_name in surface.name:
                for name in surface.name:
                    if name.isdigit():
                        return int(name)
        raise Exception(f"{surface_name} is not among available surfaces")


class SurfaceCoordinates:
    """Store rotation, offset, tilt, and comment data for a surface."""

    def __init__(self, rotation, offset, tilt, comment):
        self.rotation = rotation
        self.offset = offset
        self.tilt = tilt
        self.comment = comment

    def __repr__(self):
        return (
            f"SurfaceCoordinates(\n"
            f"  Rotation Matrix:\n{self.rotation if self.rotation is not None else 'None'}\n"
            f"  Offset Vector: {self.offset if self.offset is not None else 'None'}\n"
            f"  Tilt Vector: {self.tilt if self.tilt is not None else 'None'}\n"
            f"  Comment: {self.comment}\n"
        )


class SurfacePRD:
    """Container for parsed surface prescription and metadata."""

    def __init__(self, name):
        """
        Initialize a Surface object with a given name.
        """
        self.name = name

    def __setattr__(self, key, value):
        """
        Override attribute setting to clean up specific values like CURV, DIAM, DISZ and PARM.
        """
        super().__setattr__(key, value)

    def __repr__(self):
        """
        Represent the Surface object with its name and attributes.
        """
        return f"Surface({self.__dict__})"

    def items(self):
        """Return key-value pairs of surface properties."""
        return self.__dict__.items()
