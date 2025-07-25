import yaml

from .local_types import ConstMedium, SellmeierMedium

_NAME_AND_NODE = {}
_ID_AND_NODE = {}
_MEDIA = {}


class AnchoredValue:
    """
    Wrap a ConstMedium with a YAML anchor name for serialization.

    Parameters
    ----------
    value : object
        The optical medium value.
    anchor_name : str
        YAML anchor name to associate with the medium.
    """

    def __init__(self, value: object, anchor_name: str):
        """
        Initialize AnchoredValue with a medium and anchor.

        Parameters
        ----------
        value : object
            The optical medium.
        anchor_name : str
            The YAML anchor name.
        """
        self.value = value
        self.anchor_name = anchor_name
        _MEDIA[self.anchor_name] = self

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

    def generate_anchor(self, node):
        anchor = super().generate_anchor(node)
        _ID_AND_NODE[anchor] = node
        return anchor


def represent_anchored_value(dumper, data):
    """
    Create a YAML mapping node for an AnchoredValue.
    Handles SellmeierMedium (expands coefs) and single float ConstMedium.
    """
    medium = data.value
    mapping = {"type": medium.__class__.__name__}

    # If medium has coefs of length 6, expand as Sellmeier coefficients
    if hasattr(medium, "coefs") and len(medium.coefs) == 6:
        mapping.update(
            {
                "B1": medium.coefs[0],
                "B2": medium.coefs[1],
                "B3": medium.coefs[2],
                "C1": medium.coefs[3],
                "C2": medium.coefs[4],
                "C3": medium.coefs[5],
            }
        )
    # If medium has a single float n (ConstMedium)
    elif hasattr(medium, "n"):
        mapping["n"] = medium.n
    # Fallback: dump all public attributes as a list
    else:
        for key, val in vars(medium).items():
            if not key.startswith("_"):
                mapping[key] = val

    node = dumper.represent_mapping("tag:yaml.org,2002:map", mapping)
    _NAME_AND_NODE[data.anchor_name] = node
    return node


# Register AnchoredValue representer with the YAML dumper
AnchorDumper.add_multi_representer(AnchoredValue, represent_anchored_value)

# Register ConstMedium & SellmeierMedium representer with the YAML dumper
AnchorDumper.add_multi_representer(SellmeierMedium, represent_anchored_value)
AnchorDumper.add_multi_representer(ConstMedium, represent_anchored_value)


def ignore_aliases(self, data):
    """
    Disable PyYAML aliasing behavior for AnchoredValue types.

    Parameters
    ----------
    self : SafeRepresenter
        The representer instance.
    data : object
        The object being checked.

    Returns
    -------
    bool
        True if data should not be aliased.
    """
    return not isinstance(data, AnchoredValue)


yaml.representer.SafeRepresenter.ignore_aliases = ignore_aliases
