import numpy as np
import yaml

# Classes/methods in this file are used to parse a zemax (.zmx) file and return key parameters.
# It is also used to construct a machine-readable file that can be used by other parties
# as a reference to the optical design.


class Surface:
    """Represents an optical surface."""
    def __init__(self, name):
        """
        Initialize a Surface object with a given name.
        """
        self.name = name

    def __setattr__(self, key, value):
        """
        Override attribute setting to clean up specific values like CURV, DIAM, DISZ and PARM.
        """
        if key in ["CURV", "DISZ", "CONI"]:  # Handle CURV and DISZ specifically
            value = self._parse_first_float(value)
        elif key == "DIAM":  # Handle DIAM specifically, multiplying by 2
            value = self._parse_first_float(value) * 2
        elif key.startswith("PARM"):  # Handle PARM specifically
            param_index, param_value = self._parse_parm(value)
            key = f"PARM{param_index}"
            value = param_value
        elif key == "CLAP" or key == "ELAP":
            value = self._parse_aper(value)
        elif key == "SQAP":
            value = 2 * self._parse_aper(value)
        elif key == "OBDC":
            value = self._parse_obsc(value)
        super().__setattr__(key, value)

    @staticmethod
    def _parse_first_float(value):
        """
        Extract and return the first float value from a string.
        """
        try:
            return float(value.split()[0])  # Extract the first float
        except (ValueError, IndexError):
            return value  # Return the raw value if parsing fails

    @staticmethod
    def _parse_parm(value):
        """
        Parse a PARM line into its index and value.
        """
        try:
            parts = value.split()
            param_index = int(parts[0])  # Extract the PARM index
            param_value = float(parts[1])  # Extract the PARM value
            return param_index, param_value
        except (ValueError, IndexError) as err:
            raise ValueError(f"Invalid PARM format: {value}") from err

    @staticmethod
    def _parse_aper(value):
        """
        Parse a aperture line into its values.
        """
        try:
            parts = value.split()[:-1]
            return np.array(parts, dtype=float)
        except (ValueError, IndexError) as err:
            raise ValueError(f"Invalid APER format: {value}") from err

    @staticmethod
    def _parse_obsc(value):
        """
        Parse a aperture line into its values.
        """
        try:
            parts = value.split()
            return np.array(parts, dtype=float)
        except (ValueError, IndexError) as err:
            raise ValueError(f"Invalid APER format: {value}") from err

    def __repr__(self):
        """
        Represent the Surface object with its name and attributes.
        """
        return f"Surface(name={self.name}, attributes={self.__dict__})"

    # def __getattr__(self, name):
    #     if name in self.__dict__:
    #         return self.__dict__[name]
    #     raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def items(self):
        """Return an iterable view of (key, value) pairs, like dict.items()."""
        return self.__dict__.items()


class SystemDetails:
    """Container for optical system metadata and parameters."""
    def __init__(self):
        """
        Initialize the SystemDetails object with default attributes.
        """
        self.ENPD = None
        self.UNIT = None
        self.WAVM = []
        self.FEFD = []
        self.XFLD = []
        self.YFLD = []
        self.FLDS = []

    def __repr__(self):
        """
        Represent the SystemDetails object with its attributes.
        """
        return f"SystemDetails(ENPD={self.ENPD}, UNIT={self.UNIT}, WAVM={self.WAVM}, FEFD={self.FEFD})"


class ZemaxFileParser:
    """Parser for Zemax .ZMX files, extracting system information."""
    def __init__(self, file_path, encoding="utf-16"):
        """
        Initialize the parser with the path to the Zemax .zmx file.
        Automatically reads the file and parses all relevant data.
        """
        self.file_path = file_path
        self.encoding = encoding
        self.file_content = None
        self.surfaces = {}
        self.system_details = SystemDetails()
        self.STOP = None  # Attribute to hold the STOP surface

        # Automatically perform all parsing steps
        self._initialize_parser()

    def _initialize_parser(self):
        """
        Perform all necessary parsing steps during initialization.
        """
        self.read_file(encoding=self.encoding)
        self.parse_surfaces()
        self.identify_stop_surface()
        self.parse_system_details()

        FLDS = list(# noqa: N806
            map(
                lambda coord: list(coord),
                zip(self.system_details.XFLD, self.system_details.YFLD, strict=False),
            )
        )
        FLDS.insert(0, [0, 0])  # "insert" just to have the right indexing like in ZMX
        self.system_details.FLDS = FLDS + self.system_details.FEFD

    def read_file(self, encoding):
        """
        Reads the file with UTF-16 encoding and stores the content as text.
        """
        with open(self.file_path, "r", encoding=encoding) as file:
            self.file_content = file.readlines()

    def parse_surfaces(self):
        """
        Parses the file content to extract surface information and create Surface objects.
        """
        if not self.file_content:
            raise ValueError("File content is empty. Did you call read_file()?")

        current_surface = None
        current_surface_number = None

        for line in self.file_content:
            line = line.strip()

            if line.startswith("SURF"):  # Start of a new surface
                if current_surface:
                    # Determine the name: use COMM if present, otherwise use the surface number
                    self._store_surface(current_surface, current_surface_number)

                # Initialize a new surface
                current_surface_number = line.split(" ", 1)[-1]
                current_surface = Surface(name=current_surface_number)
            elif current_surface and line:  # Parse details of the current surface
                key_value = line.split(" ", 1)
                if len(key_value) == 2:  # Key-value pair
                    key, value = key_value
                    setattr(current_surface, key, value)
                elif len(key_value) == 1:  # Key only (e.g., "STOP")
                    key = key_value[0]
                    setattr(current_surface, key, True)  # Assign True for standalone keys like STOP

        if current_surface:
            # Store the last surface
            self._store_surface(current_surface, current_surface_number)

    def _store_surface(self, surface, surface_number):
        """
        Helper method to store a surface in the dictionary with appropriate keys.
        """
        # Store by surface number
        self.surfaces[surface_number] = surface

        # Store by COMM name if available
        comm = getattr(surface, "COMM", None)
        if comm:
            self.surfaces[comm] = surface

        # Include STOP marker in sublist keys if applicable
        surface_name = [surface_number, comm] if comm else [surface_number]
        if getattr(surface, "STOP", False):
            surface_name.append("STOP")
            self.surfaces["STOP"] = surface  # Add STOP key for direct access
        surface_name = [elem for elem in surface_name if elem]  # Remove None
        self.surfaces[tuple(surface_name)] = surface

    def identify_stop_surface(self):
        """
        Identify the STOP surface by checking all surfaces for the STOP attribute.
        """
        for surface in self.surfaces.values():
            if isinstance(surface, Surface) and getattr(surface, "STOP", False):
                self.STOP = surface
                self.surfaces["STOP"] = surface  # Ensure STOP key is available
                break

    def parse_system_details(self):
        """
        Parses the file content to extract system details like ENPD, UNIT, WAVM, and FEFD.
        """
        if not self.file_content:
            raise ValueError("File content is empty. Did you call read_file()?")

        for line in self.file_content:
            line = line.strip()

            if line.startswith("ENPD"):  # Entrance pupil diameter
                try:
                    self.system_details.ENPD = float(line.split(" ", 1)[-1])
                except ValueError:
                    self.system_details.ENPD = None
            elif line.startswith("UNIT"):  # Units
                self.system_details.UNIT = line.split(" ", 1)[-1].split()
            elif line.startswith("WAVM"):  # Wavelengths
                self.system_details.WAVM.append(line.split(" ", 1)[-1])
            elif line.startswith("FEFD"):  # Other Fields
                dummyLine = line.split(" ", 1)[-1].split() # noqa: N806
                self.system_details.FEFD.append(list(map(float, dummyLine[:2])))
            elif line.startswith("XFLN"):  # Fields X
                self.system_details.XFLD = list(map(float, line.split(" ", 1)[-1].split()))
            elif line.startswith("YFLN"):  # Fields Y
                self.system_details.YFLD = list(map(float, line.split(" ", 1)[-1].split()))

    def surface(self, key):
        """
        Retrieve a Surface object by its surface number, COMM name, or tuple key.
        """
        return self.surfaces.get(key)

    def get_surface_names(self):
        """
        Returns a list of sublists where each sublist contains the surface number,
        COMM name, and STOP if applicable.
        """
        result = []
        seen = set()

        for key, surface in self.surfaces.items():
            if isinstance(key, tuple):  # Surface names as tuples
                if key not in seen:
                    result.append(list(key))
                    seen.add(key)
            elif key.isdigit():  # Surface number only
                comm = getattr(surface, "COMM", None)
                surface_name = [key, comm] if comm else [key]
                if getattr(surface, "STOP", False):
                    surface_name.append("STOP")
                surface_name = [elem for elem in surface_name if elem]  # Remove None
                result.append(surface_name)
                seen.add(tuple(surface_name))

        return result


class PrescriptionDataParser:
    """Parses optical prescription data files to extract relevant parameters."""
    def __init__(self, file_path):
        self.file_path = file_path
        self.surface_data = {}
        self.entrance_pupil_position = None
        self.entrance_pupil_diameter = None
        self.exit_pupil_position = None
        self.exit_pupil_diameter = None
        self.extract_matrices()  # Automatically extract upon initialization
        self.extract_pupils()

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
                    self.surface_data[surface_num] = SurfacePrescriptionData(None, None, None, comment)
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

                self.surface_data[surface_num] = SurfacePrescriptionData(
                    rotation_matrix, offset_vector, tilt_vector, comment
                )

    def surface(self, surface_num):
        """Get SurfacePrescriptionData object for a specific surface."""
        surface = self.surface_data.get(str(surface_num), None)
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

                # Entrance Pupil
                if "Entrance Pupil Position" in key:
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

    def entrance_pupil_position(self):
        """Get the extracted entrance pupil position."""
        return self.entrance_pupil_position

    def entrance_pupil_diameter(self):
        """Get the extracted entrance pupil size."""
        return self.entrance_pupil_diameter

    def exit_pupil_position(self):
        """Get the extracted exit pupil position."""
        return self.exit_pupil_position

    def exit_pupil_diameter(self):
        """Get the extracted exit pupil diameter."""
        return self.exit_pupil_diameter


class SurfacePrescriptionData:
    """Holds geometric and descriptive data for a single optical surface."""
    def __init__(self, rotation, offset, tilt, comment):
        self.rotation = rotation
        self.offset = offset
        self.tilt = tilt
        self.comment = comment

    def __repr__(self):
        return (
            f"SurfacePrescriptionData(\n"
            f"  Rotation Matrix:\n{self.rotation if self.rotation is not None else 'None'}\n"
            f"  Offset Vector: {self.offset if self.offset is not None else 'None'}\n"
            f"  Tilt Vector: {self.tilt if self.tilt is not None else 'None'}\n"
            f"  Comment: {self.comment}\n"
        )


def build_yaml_file(input_file, output_file=None, encoding="utf-16"):
    """Builds a yaml file with the critical information of the optical design."""

    telescope = ZemaxFileParser(input_file, encoding=encoding)

    data = {}  # Dict that will be dumped to a YAML file

    details = telescope.system_details
    for key in vars(details):
        # Convert numpy arrays to lists to enable writing to YAML
        if isinstance(vars(details)[key], np.ndarray):
            vars(details)[key] = (vars(details)[key]).tolist()

        data[key] = vars(details)[key]

    surface_names = telescope.get_surface_names()

    for i, surf in enumerate(surface_names):
        # Now loop over all the attributes in the surface class
        # (which is a dictionary via vars)
        # and check for YAML issues
        for key in vars(telescope.surfaces[surf[0]]):
            # Convert numpy arrays to lists
            if isinstance(vars(telescope.surfaces[surf[0]])[key], np.ndarray):
                vars(telescope.surfaces[surf[0]])[key] = (vars(telescope.surfaces[surf[0]])[key]).tolist()

        data[f"surface_{i}"] = vars(telescope.surfaces[surf[0]])

    # Write to file
    with open(output_file, mode="wt", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False)

    return


###################
###################
###################

# This belongs in a README or docstrings something
#
# def main():
#     # Instantiate
#     telescope = ZemaxFileParser("STP_TMA_Mark_12F+M1_Bending_SBTest_5_HC01.zmx")

#     print("\nNAMES", telescope.get_surface_names())

#     # Example usage
#     SURF = telescope.surface("M1")

#     # Access system details as attributes
#     system_details = telescope.system_details

#     print("\n")
#     print("SURF:  ", SURF.PARM2)
#     print("THIC:   ", SURF.DISZ)
#     print("ENPD:    ", system_details.ENPD)
#     print("STOP:", telescope.STOP)
#     print("UNIT:", system_details.UNIT)


# if __name__ == "__main__":
#     main()
