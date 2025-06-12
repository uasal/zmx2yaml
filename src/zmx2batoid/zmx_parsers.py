import numpy as np
import os

class Surface:
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
        except (ValueError, IndexError):
            raise ValueError(f"Invalid PARM format: {value}")
    
    @staticmethod
    def _parse_aper(value):
        """
        Parse a aperture line into its values.
        """
        try:
            parts = value.split()[:-1]
            return np.array(parts, dtype=float)
        except (ValueError, IndexError):
            raise ValueError(f"Invalid APER format: {value}")
        
    @staticmethod
    def _parse_obsc(value):
        """
        Parse a aperture line into its values.
        """
        try:
            parts = value.split()
            return np.array(parts, dtype=float)
        except (ValueError, IndexError):
            raise ValueError(f"Invalid APER format: {value}")

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
        return self.__dict__.items()

class SystemDetails:
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
    def __init__(self, file_path, encoding='utf-16'):
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

        FLDS = list(map(lambda coord: list(coord), zip(self.system_details.XFLD, self.system_details.YFLD)))
        FLDS.insert(0, [0, 0]) # "insert" just to have the right indexing like in ZMX
        self.system_details.FLDS = FLDS + self.system_details.FEFD

    def read_file(self, encoding):
        """
        Reads the file with UTF-16 encoding and stores the content as text.
        """
        with open(self.file_path, 'r', encoding=encoding) as file:
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
                dummyLine = line.split(" ", 1)[-1].split()
                self.system_details.FEFD.append(list(map(float, dummyLine[:2])))
            elif line.startswith("XFLN"): # Fields X
                self.system_details.XFLD = list(map(float, line.split(" ", 1)[-1].split()))
            elif line.startswith("YFLN"): # Fields Y
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
    def __init__(self, file_path):
        self.file_path = file_path
        self.surface_coordinates = {}
        self.entrance_pupil_position = None
        self.entrance_pupil_diameter = None
        self.exit_pupil_position = None
        self.exit_pupil_diameter = None
        self.extract_matrices()  # Automatically extract upon initialization
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
        with open(self.file_path, 'r') as file:
            lines = file.readlines()

        lines_iter = iter(lines)
        for line in lines_iter:
            stripped_line = line.lstrip().split()  # Handle lines with leading spaces
            if len(stripped_line) >= 6 and stripped_line[0].isdigit() and self._is_numeric_list(stripped_line[1:6]):
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

                if len(line2) >= 5 and len(line3) >= 5 and self._is_numeric_list(line2[:5]) and self._is_numeric_list(line3[:5]):
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

                self.surface_coordinates[surface_num] = SurfaceCoordinates(rotation_matrix, offset_vector, tilt_vector, comment)

    def coordinates(self, surface_num):
        """Get SurfaceCoordinates object for a specific surface."""
        surface = self.surface_coordinates.get(str(surface_num), None)
        if surface is None:
            print(f"Warning: Surface {surface_num} not found.")
        return surface
    
    def extract_pupils(self):
        """Extract entrance and exit pupil positions and sizes from the file without using regex."""
        with open(self.file_path, 'r') as file:
            lines = file.readlines()

        for line in lines:
            parts = line.split(":")  # Split at ":" to separate labels from values

            if len(parts) > 1:
                key = parts[0].strip()
                value = parts[1].strip()

                # File name
                if key == "File": # to ensure it is one 'File' which is found and not another line finishing by 'File'
                    try:
                        drive = value
                        rest_of_path = parts[2].strip()
                        full_path = f"{drive}:{rest_of_path}"
                        norm_path = full_path.replace("\\", "/")
                        self.filename = os.path.splitext(os.path.basename(norm_path))[0] # import os
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

    def extract_fields(self):
        fields = []

        with open(self.file_path, 'r') as file:
            lines = file.readlines()

            field_i = 1
            offset_i = 1
            field_flag = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(":", 1)  # Only split on first ":"
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                if "Fields" in key:
                    field_flag = True
                    nb_fields = int(value)
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
        waves = []

        with open(self.file_path, 'r') as file:
            lines = file.readlines()

            units = None
            wave_i = 1
            offset_i = 1
            waves_flag = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(":", 1)  # Only split on first ":"
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                if key == 'Wavelengths':
                    waves_flag = True
                    nb_fields = int(value)
                    continue
                if waves_flag:
                    if "Units" in key:
                        units = value
                    if offset_i <= 2:
                        offset_i += 1
                        continue
                    elif wave_i <= nb_fields:
                        key_parts = key.split()
                        waves.append(float(key_parts[1]))
                        wave_i += 1
                        continue
                    else:
                        waves = [w * 1e-6 for w in waves] if units == '?m' else (waves)
                        break
        self.waves = waves

    def extract_surface(self):
        def is_float(s):
            s = s.strip()
            if s.lstrip("+-").isdigit():
                return True  # it's an integer
            if s.count('.') == 1:
                left, right = s.split('.')
                if left.lstrip("+-").isdigit() and right.isdigit():
                    return True  # it's a float
            return False
        
        surfaces = {}
        surface_i = 0
        surface_nb = self.surface_nb

        offset_i = 1

        in_data_summary_flag = False

        with open(self.file_path, 'r') as file:
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
                    if surface_i <= surface_nb:
                        key_parts = key.split("\t")
                        surf_line = key_parts + [''] if len(key_parts) == 9 else (key_parts)
                        surf_line = [s.replace(" ", "") for s in surf_line[:-1]] + [surf_line[-1].strip()]

                        NAME = [str(surface_i), surf_line[0]] if not surf_line[-1] else [str(surface_i), surf_line[0], surf_line[-1]]
                        current_surface = SurfacePRD(name=list(set(NAME)))

                        setattr(current_surface, 'TYPE', surf_line[1])

                        CURV = 1/float(surf_line[2]) if is_float(surf_line[2]) else (0.0)
                        setattr(current_surface, 'CURV', CURV)

                        DISZ = float(surf_line[3]) if is_float(surf_line[3]) else (0.0)
                        setattr(current_surface, 'DISZ', DISZ)

                        GLAS = surf_line[4]
                        if GLAS:
                            setattr(current_surface, 'GLAS', surf_line[4])

                        DIAM = float(surf_line[5]) if is_float(surf_line[5]) else (None)
                        if DIAM is not None:
                            setattr(current_surface, 'DIAM', DIAM)

                        CONI = float(surf_line[-2]) if is_float(surf_line[-2]) else (None)
                        if CONI is not None:
                            setattr(current_surface, 'CONI', CONI)

                        COMM = surf_line[-1]+':'+value if value else (surf_line[-1])
                        if COMM:
                            setattr(current_surface, 'COMM', COMM)

                        surfaces[str(surface_i)] = current_surface
                        
                        surface_i += 1
                    else:
                        break
        self.surfaces = surfaces

    def extract_surface_details(self): 
        surface_i = 0
        surface_nb = self.surface_nb

        offset_i = 1

        in_data_details_flag = False

        aper_type = None
        OBDC = [0.0, 0.0]
        APER = [0.0, 0.0]
        PARM = []
        XDAT = []
        is_aper = None

        with open(self.file_path, 'r') as file:
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
                    if not key: # meaning empty line i.e. end of a surface
                        current_surface = self.surfaces[str(surface_i)]
                        if any(OBDC):
                            setattr(current_surface, 'OBDC', np.array(OBDC))
                        if aper_type is not None:
                            setattr(current_surface, aper_type, np.array(APER))
                        if is_aper is not None:
                            setattr(current_surface, 'ISAP', int(is_aper))
                        if PARM:
                            for j in range(len(PARM)):
                                setattr(current_surface, f'PARM{j+1}', PARM[j])
                        if XDAT:
                            for j in range(len(XDAT)):
                                setattr(current_surface, f'XDAT{j+1}', XDAT[j])


                        aper_type = None
                        is_aper = None
                        OBDC = [0.0, 0.0]
                        APER = [0.0, 0.0]
                        PARM = []
                        XDAT = []

                        surface_i += 1
                        continue
                    if surface_i <= surface_nb:
                        if key.startswith("Surface"):
                            if key.split()[1] in self.surfaces[str(surface_i)].name:
                                surf_type = self.surfaces[str(surface_i)].TYPE
                                continue
                            else:
                                raise Exception("ERROR")
                        else:
                            if key.startswith("Aperture"):
                                ap = value.split()[0]
                                aper_type = 'ELAP' if ap == 'Elliptical' else ('SQAP' if ap == 'Rectangular' else ('CLAP' if ap == 'Circular' else (None)))
                                is_aper = value.split()[1] == 'Aperture'
                                continue

                            if key.startswith("Minimum Radius"):
                                APER[0] = float(value)
                                continue
                            elif key.startswith("Maximum Radius"):
                                APER[1] = float(value)
                                continue
                            elif key.startswith("X Half Width"):
                                APER[0] = float(value) * 2 if aper_type == 'SQAP' else (float(value))
                                continue
                            elif key.startswith("Y Half Width"):
                                APER[1] = float(value) * 2 if aper_type == 'SQAP' else (float(value))
                                continue

                            if key.startswith("X- Decenter"):
                                OBDC[0] = float(value)
                                continue
                            elif key.startswith("Y- Decenter"):
                                OBDC[1] = float(value)

                            if surf_type == "COORDBRK":
                                if key.startswith("Order"):
                                    PARM.append(0 if value == "Decenter then tilt" else (1))
                                else:
                                    PARM.append(float(value))
                                continue
                            elif surf_type == "EVENASPH":
                                if key.startswith("Coefficient"):
                                    PARM.append(float(value))
                                    continue
                            elif surf_type == "BICONICX":
                                if key.startswith("X Radius") or key.startswith("X Conic"):
                                    PARM.append(float(value))
                                    continue
                            elif surf_type == "SZERNSAG":
                                if key.startswith("Coefficient") or key.startswith("Zernike Decenter"):
                                    PARM.append(float(value))
                                    continue
                                if key.startswith("Number") or key.startswith("Normalization") or key.startswith("Zernike Term"):
                                    XDAT.append(float(value))
                                    continue
                    else:
                        break

    def extract_surface_index(self): 
        surface_i = 0
        surface_nb = self.surface_nb

        offset_i = 1

        in_index_flag = False
        has_glas = False

        with open(self.file_path, 'r') as file:
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
                    if surface_i <= surface_nb:
                        key_parts = key.split("\t")
                        current_surface = self.surfaces[str(surface_i)]
                        if key_parts[0].strip() in current_surface.name:
                            has_glas = hasattr(current_surface, 'GLAS')
                        if has_glas and current_surface.GLAS != 'MIRROR':
                            index = float(key_parts[4].strip())
                            setattr(current_surface, 'GLAS', " ".join([current_surface.GLAS, str(index)]))
                        surface_i += 1
                    else:
                        break

    def extract_multi_configurations(self):
        configurations = {}
        current_config = None
        in_configuration = False  # Tracks if we are inside a config block

        with open(self.file_path, 'r') as file:
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
                    elif key.split()[1] == 'Comment':
                        configurations[current_config][key] = value
                    else:
                        configurations[current_config][' '.join(key.split())] = float(value_parts[0])

        self.configurations = configurations


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
    
    def surface(self, surface_name):
        """
        Retrieve a Surface object by its surface number, COMM name, or tuple key.
        """
        for surface in self.surfaces.values():
            if surface_name in surface.name:
                return surface
        raise Exception(f'{surface_name} is not among available surfaces')
    
    def get_surface_num(self, surface_name):
        for surface in self.surfaces.values():
            if surface_name in surface.name:
                for name in surface.name:
                    if name.isdigit():
                        return int(name)
        raise Exception(f'{surface_name} is not among available surfaces')


    

class SurfaceCoordinates:
    def __init__(self, rotation, offset, tilt, comment):
        self.rotation = rotation
        self.offset = offset
        self.tilt = tilt
        self.comment = comment

    def __repr__(self):
        return (f"SurfaceCoordinates(\n"
                f"  Rotation Matrix:\n{self.rotation if self.rotation is not None else 'None'}\n"
                f"  Offset Vector: {self.offset if self.offset is not None else 'None'}\n"
                f"  Tilt Vector: {self.tilt if self.tilt is not None else 'None'}\n"
                f"  Comment: {self.comment}\n")

class SurfacePRD:
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
        return self.__dict__.items()
    
    



    

###################
###################
###################
 
def main():
    import numpy as np

if __name__=='__main__':
    main()