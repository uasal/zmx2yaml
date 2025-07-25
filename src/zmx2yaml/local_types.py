import importlib.util

_BATOID_AVAILABLE = importlib.util.find_spec("batoid") is not None


class ConstMedium:
    """ConstMedium compatible with both local and batoid implementations."""

    def __new__(cls, n):
        """Create a new ConstMedium instance."""
        if _BATOID_AVAILABLE:
            import batoid

            return batoid.ConstMedium(n)
        return super().__new__(cls)

    def __init__(self, n):
        """Initialize ConstMedium with refractive index n."""
        self.n = n

    def __repr__(self):
        """Return string representation of ConstMedium."""
        return f"ConstMedium({self.n})"


class SellmeierMedium:
    """SellmeierMedium compatible with both local and batoid implementations."""

    def __new__(cls, coefs):
        """Create a new SellmeierMedium instance from a list or tuple of 6 coefficients."""
        if _BATOID_AVAILABLE:
            import batoid

            return batoid.SellmeierMedium(coefs)
        return super().__new__(cls)

    def __init__(self, coefs):
        """Initialize SellmeierMedium with Sellmeier coefficients as a tuple in coefs."""
        if len(coefs) != 6:
            raise ValueError("SellmeierMedium requires 6 coefficients (B1, B2, B3, C1, C2, C3)")
        self.coefs = tuple(coefs)

    def __repr__(self):
        """Return string representation of SellmeierMedium."""
        return f"SellmeierMedium({self.coefs})"
