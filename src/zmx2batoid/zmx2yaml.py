"""
ZMX to YAML Conversion Module

This module converts Zemax prescription files to YAML format
suitable for use with Batoid optics simulations.

Author: Pierre Raphaël Nicolas
Date: 05/30/2025
"""

import numpy as np
import yaml

from zmx2batoid.zmx_parsers_old import PrescriptionDataParser
from batoid.medium import ConstMedium
from batoid.optic import Optic

##############################
####  Anchor index values ####
##############################

class AnchoredValue:
    """
    Wrap a ConstMedium with a YAML anchor name for serialization.

    Parameters
    ----------
    value : ConstMedium
        The optical medium value.
    anchor_name : str
        YAML anchor name to associate with the medium.
    """
    def __init__(self, value: ConstMedium, anchor_name: str):
        """
        Initialize AnchoredValue with a medium and anchor.

        Parameters
        ----------
        value : ConstMedium
            The optical medium.
        anchor_name : str
            The YAML anchor name.
        """
        self.value = value
        self.anchor_name = anchor_name

    def __repr__(self):
        """
        Return string representation showing anchor name.

        Returns
        -------
        str
            A string showing the YAML anchor name.
        """
        return f"AnchoredValue(name={self.anchor_name})"


class AnchorDumper(yaml.SafeDumper):
    """
    Custom PyYAML dumper class used to emit AnchoredValue objects
    with anchors in the YAML output.
    """
    pass


def represent_anchored_value(dumper, data):
    """
    Create a YAML mapping node for an AnchoredValue.

    Parameters
    ----------
    dumper : yaml.Dumper
        PyYAML dumper object.
    data : AnchoredValue
        Anchored medium to serialize.

    Returns
    -------
    yaml.Node
        Mapping node with an anchor for YAML output.
    """
    medium = data.value
    mapping = {'type': medium.__class__.__name__}

    for key, val in vars(medium).items():
        if not key.startswith("_"):
            mapping[key] = val

    node = dumper.represent_mapping('tag:yaml.org,2002:map', mapping)
    node.anchor = data.anchor_name
    return node


# Register AnchoredValue representer with the YAML dumper
AnchorDumper.add_multi_representer(AnchoredValue, represent_anchored_value)


def ignore_aliases(_, data):
    """
    Disable PyYAML aliasing behavior for AnchoredValue types.

    Parameters
    ----------
    _ : Any
        Unused.
    data : object
        The object being checked.

    Returns
    -------
    bool
        True if data should not be aliased.
    """
    return not isinstance(data, AnchoredValue)


yaml.representer.SafeRepresenter.ignore_aliases = ignore_aliases

##############################
##############################
##############################

# Global medium for air
global AIR
AIR = AnchoredValue(ConstMedium(1.0), "air")

class ZMX2YAML:
    """
    Convert Zemax prescriptions into Batoid optics and export them to YAML.

    This class parses a Zemax file using a custom parser, selects specific surfaces,
    applies field bias and entrance pupil settings, and exports the resulting Batoid
    Optic as a YAML dictionary. It also ensures all media are properly anchored in
    the YAML output for reuse.

    Parameters
    ----------
    PRD_FILE_NAME : str
        Path to the Zemax prescription (.ZMX) file.
    WANTED_SURF_LIST : list of str or int
        List of surface names or indices to extract from the prescription.
    ENPP : list of str or int, optional
        Surface(s) used to define the entrance pupil. Defaults to the first in WANTED_SURF_LIST.
    FIELD_BIAS : list of float, optional
        Field bias to apply when generating the optical system.
    """
    def __init__(self, PRD_FILE_NAME=None, WANTED_SURF_LIST=[], ENPP=[], FIELD_BIAS=[]):
        """
        Initialize the converter with a Zemax file and conversion settings.

        Parameters
        ----------
        PRD_FILE_NAME : str, optional
            Path to the Zemax ZMX prescription file.
        WANTED_SURF_LIST : list of str or int
            Surface names or indices to include in the output.
        ENPP : list of str or int, optional
            Surfaces representing the entrance pupil.
        FIELD_BIAS : list of float, optional
            Field bias values to apply to the parsed prescription.
        Raises
        ------
        Exception
            If PRD_FILE_NAME or WANTED_SURF_LIST is missing.
        """
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

        self.conv_coef = 1000 if 'Millimeters' in self.PRD_FILE.unit else (1) # Conversion to meters if not
    
    def extract_asphere_coefs(self, surface: PrescriptionDataParser.surface) -> list:
        """
        Extract aspheric surface coefficients from a prescription surface and convert them.

        Parameters
        ----------
        surface : PrescriptionDataParser.surface
            The surface object containing asphere parameters.

        Returns
        -------
        list
            List of converted aspheric coefficients.
        """
        converted_params_corrected = [0] * 8 # r^2, r^4, r^6, r^8, r^10, r^12, r^14, r^16
        for key, value in surface.items():
            if key.startswith("PARM"):
                index = int(key[4:])  # PARM1 -> index 1, PARM2 -> index 2, etc.
                if index > 8:
                    break  # Stop after PARM8
                exponent = np.log10(self.conv_coef) * (2 * index - 1)  # Compute the conversion exponent
                converted_value = value * (10 ** exponent)  # Apply conversion
                converted_params_corrected[index - 1] = float(converted_value)
        return converted_params_corrected
    
    def extract_zernike_coefs(self, surface: PrescriptionDataParser.surface) -> list:
        """
        Extract Zernike polynomial coefficients from a prescription surface.

        Parameters
        ----------
        surface : PrescriptionDataParser.surface
            Surface containing Zernike data fields (e.g., XDAT3, XDAT4...).

        Returns
        -------
        list
            List of Zernike coefficients.
        """
        znk = [0] * int(surface.XDAT1)  # Total number of Zernike coefficients
        for key, value in surface.items():
            if key.startswith("XDAT") and key not in ("XDAT1", "XDAT2"):
                index = int(key[4:]) - 3  # XDAT3 -> index 0, XDAT4 -> index 1, etc.
                znk[index] = value
        return znk

    @staticmethod
    def medium(n: float) -> ConstMedium:
        """
        Create a constant-index medium for use in an optical model.

        Parameters
        ----------
        n : float
            Refractive index value of the medium.

        Returns
        -------
        ConstMedium
            Batoid medium with constant index `n`.
        """
        return ConstMedium(n)

    @staticmethod
    def insert_swapped_mediums(a: Optic, b: Optic) -> Optic:
        """
        Replace all mediums in optic `a` by those from optic `b` with matching anchors.

        Parameters
        ----------
        a : Optic
            Target optic where mediums will be replaced.
        b : Optic
            Source optic providing the AnchoredValue-wrapped mediums.

        Returns
        -------
        Optic
            New optic object with swapped mediums.
        """
        new_b = {}
        for key in a:
            if key == 'inMedium':
                new_b[key] = a['outMedium']  # swap!
            elif key == 'outMedium':
                new_b[key] = a['inMedium']  # swap!
            elif key in b:
                new_b[key] = b[key]
        # Add any other fields from b that aren’t in a (fallback)
        for key in b:
            if key not in new_b:
                new_b[key] = b[key]
        return new_b
        
    def build_dict_surf(self, SURF_name: int | str) -> dict:
        """
        Build a surface dictionary for a specific optical surface.

        Parameters
        ----------
        SURF_name : int or str
            Index or name of the surface.

        Returns
        -------
        dict
            Dictionary describing the surface parameters.
        """
        SURF_name = str(SURF_name) if isinstance(SURF_name, int) else (SURF_name)
        surface = self.PRD_FILE.surface(SURF_name)
        conv_coef = self.conv_coef
        
        curv = surface.CURV
        R = np.inf if not np.any(curv) else 1.0 / (curv * conv_coef)

        # Plane case
        if R == np.inf:
            return {'type': 'Plane'}
        
        conic = getattr(surface, 'CONI', 0.0)

        if surface.TYPE == 'STANDARD':
            shape_type = 'Paraboloid' if conic == -1 else 'Quadric'
            return {
                'type': shape_type,
                'R': R,
                'conic': conic
            }
        elif surface.TYPE == 'EVENASPH':
            coefs = self.extract_asphere_coefs(surface)
            return {
                'type': 'Asphere',
                'imin': 1,
                'R': R,
                'conic': conic,
                'coefs': coefs
            }
        elif surface.TYPE == 'BICONICX':
            conicY = conic
            conicX = getattr(surface, 'PARM2', 0.0)
            Rx = getattr(surface, 'PARM1', 0.0) / conv_coef
            return {
                'type': 'Biconic',
                'Ry': R,
                'Rx': Rx,
                'ky': conicY,
                'kx': conicX
            }
        elif surface.TYPE == 'SZERNSAG':
            norm_rad = getattr(surface, 'XDAT2', 0.0) / self.conv_coef
            znk_coefs = self.extract_zernike_coefs(surface)
            asph_coefs = self.extract_asphere_coefs(surface)
            surfaces = [{'type': 'Asphere', 'imin': 1, 'R': R, 'conic': conic, 'coefs': asph_coefs},
                        {'type': 'Zernike', 'coef': znk_coefs, 'R_outer': norm_rad, 'R_inner': 0.}]
            return {
                'type': 'Sum',
                'items': surfaces
            }

    def build_dict_obsc(self, SURF_name: int | str) -> dict:
        """
        Build an obscuration dictionary for a given surface.

        Parameters
        ----------
        SURF_name : int or str
            Name or index of the obscured surface.

        Returns
        -------
        dict
            Obscuration information dictionary.
        """
        SURF_name = str(SURF_name) if isinstance(SURF_name, int) else (SURF_name)
        conv_coef = self.conv_coef
        surface = self.PRD_FILE.surface(SURF_name)

        obdc = getattr(surface, 'OBDC', None)
        decents = list(map(float, obdc / conv_coef)) if obdc is not None else [0.0, 0.0]
        is_ap = getattr(surface, 'ISAP', 1)

        shape_defs = {
            'CLAP': ('Annulus', ['inner', 'outer']),
            'ELAP': ('Ellipse', ['semi_major', 'semi_minor']),
            'SQAP': ('Rectangle', ['width', 'height']),
        }

        for attr, (shape_type, keys) in shape_defs.items():
            data = getattr(surface, attr, None)
            if data is not None:
                dims = list(map(float, data / conv_coef))
                return {
                    'type': "Clear"+shape_type if bool(is_ap) else ("Obsc"+shape_type),
                    'x': decents[0],
                    'y': decents[1],
                    **dict(zip(keys, dims))
                }
        
        return {
            'type': 'ClearCircle',
            'x': decents[0],
            'y': decents[1],
            'radius': surface.DIAM / conv_coef
        }
                
    def build_dict_crds(self, SURF_name: int | str) -> dict:
        """
        Build a coordinate system dictionary for a given surface.

        Parameters
        ----------
        SURF_name : int or str
            Surface identifier to extract the coordinate break from.

        Returns
        -------
        dict
            Dictionary with coordinate system changes.
        """
        SURF_name = str(SURF_name) if isinstance(SURF_name, int) else (self.PRD_FILE.get_surface_num(SURF_name))
        conv_coef = self.conv_coef

        rotCenter = list(map(float, self.PRD_FILE.coordinates(SURF_name).offset / conv_coef))
        angles = list(map(float, np.deg2rad(self.PRD_FILE.coordinates(SURF_name).tilt)))
        return {
            'x': rotCenter[0],
            'y': rotCenter[1],
            'z': rotCenter[2],
            'rotX': angles[0],
            'rotY': angles[1],
            'rotZ': angles[2]
        }
    
    def build_dict_optc(self, SURF_name: int | str) -> dict:
        """
        Build an optical surface dictionary for a lens or mirror.

        Parameters
        ----------
        SURF_name : int or str
            Index or name of the optical surface.

        Returns
        -------
        dict
            Dictionary representing a Batoid optical surface.
        """
        SURF_name = str(SURF_name) if isinstance(SURF_name, int) else (SURF_name)
        surface = self.PRD_FILE.surface(SURF_name)

        glas = getattr(surface, 'GLAS', None) # returns None in does not exist
        is_mirror = isinstance(glas, str) and glas.startswith('MIRROR')
        is_refact = isinstance(glas, str) and not glas.startswith('MIRROR')
        
        MED = AnchoredValue(self.medium(float(glas.split()[1])), str(glas.split()[0])) if is_refact else AIR

        return {
            'type': 'Mirror' if is_mirror else ('RefractiveInterface'),
            'name': getattr(surface, 'COMM', SURF_name),
            **(
                {'inMedium': AIR, 'outMedium': MED} if is_refact else {}
                ),
            'surface': self.build_dict_surf(SURF_name),
            'obscuration': self.build_dict_obsc(SURF_name),
            'coordSys': self.build_dict_crds(SURF_name)
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
            'type': 'Interface',
            'name': 'ENPP',
            'surface': {
                'type': 'Plane'
            },
            'coordSys': self.build_dict_crds(self.ENPP[0])
        }
    
    def build_dict_dctr(self) -> dict:
        """
        Build the dictionary for the detector surface.

        Returns
        -------
        dict
            Dictionary with detector surface properties.
        """
        last_key = next(reversed(self.PRD_FILE.surfaces))
        SURF_name = self.PRD_FILE.surfaces[last_key].name[0]
        surface = self.PRD_FILE.surface(SURF_name)
        return {
            'type': 'Detector',
            'name': getattr(surface, 'COMM', SURF_name),
            'surface': self.build_dict_surf(SURF_name),
            'obscuration': self.build_dict_obsc(SURF_name),
            'coordSys': self.build_dict_crds(SURF_name)
        }
    
    def build_dict_meta(self) -> dict:
        """
        Generate metadata for the entire optical system.

        Returns
        -------
        dict
            Dictionary containing system-level metadata (e.g., title, author).
        """
        wavelengths = sorted(self.PRD_FILE.waves)

        return {
            'metaData': {
                'file': self.PRD_FILE.filename,
                **({'margin': self.PRD_FILE.clear_semi_diam_margin} if getattr(self.PRD_FILE, 'clear_semi_diam_margin', None) is not None else {}),
                **({'fieldBias': self.PRD_FILE.surface(self.FIELD_BIAS[0]).PARM3} if hasattr(self, 'FIELD_BIAS') else {}),
                'exitPupilSize': self.PRD_FILE.exit_pupil_diameter / self.conv_coef,
                'wavelengths': wavelengths,
                'fields': self.PRD_FILE.fields,
                **(
                    {'Configurations': self.PRD_FILE.configurations} if self.PRD_FILE.configurations is not None else {}
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
        items = [self.build_dict_optc(surf) for surf in self.WANTED_SURF_LIST]
        for i, (a, b) in enumerate(zip(items, items[1:])):
            if a['type'] == 'RefractiveInterface' and b['type'] == 'RefractiveInterface':
                b['obscuration'] = a['obscuration']
                items[i+1] = self.insert_swapped_mediums(a, b)  # Reassign updated b
        items.append(self.build_dict_dctr())

        return {
            'opticalSystem': {
                'type': 'CompoundOptic',
                'inMedium': AIR,
                'outMedium': AIR,
                'medium': AIR,
                'backDist': self.PRD_FILE.entrance_pupil_position / conv_coef,
                'sphereRadius': self.PRD_FILE.exit_pupil_position / conv_coef,
                'pupilSize': self.PRD_FILE.entrance_pupil_diameter / conv_coef,
                # 'pupilObscuration': 0.0,
                'stopSurface': self.build_dict_stop(),
                'items': items
            }
        }
    
    def build_dict_file(self) -> dict:
        """
        Compile all optical system components and metadata into one dictionary.

        Returns
        -------
        dict
            Full optical system definition ready to be serialized.
        """
        return self.build_dict_opsy() | self.build_dict_meta()

    def write_yaml(self, NAME: str) -> None:
        """
        Write the current optical system dictionary to a YAML file.

        Parameters
        ----------
        NAME : str
            File name or path to write the YAML output to.

        Returns
        -------
        None
        """
        with open(NAME+'.yaml', 'w') as f:
            yaml.dump(
                self.build_dict_file(),
                f,
                Dumper=AnchorDumper,
                sort_keys=False,          # Keep field order if possible
                default_flow_style=False, # Force expanded block style
                indent=2,                 # 2 spaces
                width=80,                 # Wrap lines sensibly
                allow_unicode=True        # In case non-ASCII names show up
            )


if __name__ == '__main__':
    _PATH = '/Users/pierrenicolas/Documents/UASAL/stp_batoid/Batoid4LOFT/support_data/Lazuli/STOP/'
    _PRD_FILE_NAME = _PATH + f"Lazuli_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt"
    
    ZMX2YAML(PRD_FILE_NAME=_PRD_FILE_NAME, WANTED_SURF_LIST=[7, 8, 9, 11], ENPP=[3], FIELD_BIAS=[5]).write_yaml(f'LAZULI STOP')