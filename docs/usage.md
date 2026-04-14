# zmx2yaml — User Guide

## What is zmx2yaml?

`zmx2yaml` converts Zemax OpticStudio optical prescription text exports (`.txt`) into YAML files
formatted for use with the [Batoid](https://github.com/jmeyers314/batoid) ray-tracing package.
It parses surface geometry, obscurations, coordinate systems, optical media, wavelengths, fields,
and system metadata, then writes them as structured, human-readable YAML.

---

## Installation

From the repository root:

```bash
pip install -e .
```

Requires Python ≥ 3.11. `numpy` and `pyyaml` must be available.
[`batoid`](https://github.com/jmeyers314/batoid) is optional: if installed, `ConstMedium` and
`SellmeierMedium` objects are constructed as native Batoid types; otherwise plain Python fallbacks
are used.

---

## Input format

The input must be a Zemax **prescription text export** (`.txt`), not a binary `.zmx` file.
In Zemax OpticStudio: *Reports → Prescription Data → Save as Text*.

The export must include all of the following sections (enabled in the prescription report settings):

- **General Data**: system-level parameters including entrance/exit pupils, lens units, fields, and wavelengths
- **Surface Data**: tabular summary of all surfaces (type, radius, thickness, glass, semi-diameter, conic constant)
- **Surface Detail**: per-surface detail including apertures, parameters, and extra data for non-standard surface types
- **Edge Thickness** *(optional, recommended)*: edge thickness of each lens element at its clear aperture boundary
- **Multi-Config Data**: multi-configuration operands and their values across all defined configurations — *note: multi-config is not supported; export one prescription file per configuration and run the script once per configuration to obtain one YAML file per configuration*
- **Solves/Variables** *(optional, recommended)*: active solves and variable definitions applied to surface parameters
- **Index/TCE Data**: refractive indices and thermal coefficients of expansion for each glass at each wavelength
- **Global Vertex**: position of each surface vertex in the global coordinate system
- **COC Point** *(optional, recommended)*: centre-of-curvature coordinates for each surface in the global frame
- **Element Volume** *(optional, recommended)*: volume and mass estimates for each lens element
- **F/Numbers**: F/number and numerical aperture data at each surface
- **Cardinal Points**: focal lengths, principal planes, nodal planes, and other cardinal point positions
- **POP Settings** *(optional, recommended)*: Physical Optics Propagation beam and sampling configuration
- **Files Used**: list of glass catalog and other external files referenced by the design

---

## Quick start — command-line script

```
python scripts/YAML_from_ZMX.py  <prd_file>  <surf1> [surf2 ...]  <output.yaml>
                                  [--enpp <s>]
                                  [--field_bias <s>]
```

| Argument | Required | Description |
|---|---|---|
| `prd_file` | yes | Path to the Zemax prescription `.txt` export |
| `surf1 surf2 …` | yes | Integer surface numbers to include in the output |
| `output.yaml` | yes | Path for the generated YAML file |
| `--enpp` | no | Single surface number defining the entrance pupil position |
| `--field_bias` | no | Single surface number whose `PARM3` is read as field bias |

### Examples

**Simple telescope (4 mirrors, entrance pupil at surface 3):**
```bash
python scripts/YAML_from_ZMX.py \
  tests/test_data/Ultramarine_Mark-11_DKim1_Release_HChoi02_prescriptiondata.txt \
  7 8 9 11 \
  tests/test_data/UM.yaml \
  --enpp 3 --field_bias 5
```

**Complex instrument (many surfaces, several configs):**
```bash
python scripts/YAML_from_ZMX.py \
  tests/test_data/Lazuli_Mark-14_17_ESC07_HK02_2_KVG_HChoi08_HK01_conf2.txt \
  3 7 8 11 15 17 26 27 33 43 45 50 53 54 59 63 67 69 71 72 73 74 79 82 83 89 98 99 104 105 106 107 110 113 \
  tests/test_data/Lazuli_Mark-14_17_ESC07_HK02_2_KVG_HChoi08_HK01_conf2.yaml \
  --enpp 3 --field_bias 5
```

---

## Python API

```python
from zmx2yaml import ZMX2YAML

obj = ZMX2YAML(
    prd_file_name   = "my_system.txt",
    wanted_surf_list= [7, 8, 9, 11],   # surface numbers to include
    enpp            = [3],             # entrance pupil surface — single surface number; defaults to wanted_surf_list[0]
    field_bias      = [5],             # field-bias surface — single surface number (optional)
)
obj.write_yaml("my_system.yaml")
```

You can also access the parsed prescription data independently:

```python
from zmx2yaml import PrescriptionDataParser

prd = PrescriptionDataParser("my_system.txt")
print(prd.surface_nb)        # total number of surfaces
print(prd.unit)              # "Millimeters", etc.
print(prd.waves)             # list of wavelengths in metres
print(prd.fields)            # list of [x, y] field coordinates
print(prd.glass_catalogs)    # e.g. ["SCHOTT", "OHARA"]

surf = prd.surface("M1")    # look up by name or surface number
print(surf.CURV)             # curvature
print(surf.CONI)             # conic constant
```

---

## Output YAML structure

The generated YAML has two top-level keys:

```yaml
opticalSystem:          # Batoid CompoundOptic
  ...
metaData:               # System-level metadata
  ...
```

### `opticalSystem`

```yaml
opticalSystem:
  type: CompoundOptic
  inMedium: &AIR           # YAML anchor — reused everywhere via *AIR
    type: ConstMedium
    n: 1.0
  outMedium: *AIR
  medium: *AIR
  backDist: -3.5           # metres
  sphereRadius: 4.1        # exit pupil sphere radius, metres
  pupilSize: 1.5           # entrance pupil diameter, metres
  stopSurface:
    type: Interface
    name: enpp
    surface:
      type: Plane
    coordSys: { x: 0.0, y: 0.0, z: 0.0, rotX: 0.0, rotY: 0.0, rotZ: 0.0 }
  items:
    - ...                  # one entry per converted surface (see below)
    - type: Detector       # always the last item (IMA surface)
      ...
```

### `metaData`

```yaml
metaData:
  file: my_system.txt
  glassCatalogs: [SCHOTT, OHARA]
  margin: 0.001            # clear semi-diameter margin (if present)
  fieldBias: 0.0           # PARM3 of field-bias surface (if --field_bias given)
  exitPupilSize: 0.06
  wavelengths: [6.28e-07, 7.65e-07]   # metres, sorted
  fields: [[0.0, 0.0], [0.0, 0.5]].  # degrees, sorted like in Zemax file
```

---

## What is automatically converted

### Global system data

| Zemax data | Parsed attribute | Output location |
|---|---|---|
| Filename (`File:`) | `prd.filename` | `metaData.file` |
| Lens units | `prd.unit` | used for unit conversion (mm → m) |
| Total surface count | `prd.surface_nb` | internal use |
| Entrance pupil position | `prd.entrance_pupil_position` | `opticalSystem.backDist` |
| Entrance pupil diameter | `prd.entrance_pupil_diameter` | `opticalSystem.pupilSize` |
| Exit pupil position | `prd.exit_pupil_position` | `opticalSystem.sphereRadius` |
| Exit pupil diameter | `prd.exit_pupil_diameter` | `metaData.exitPupilSize` |
| Glass catalogs | `prd.glass_catalogs` | `metaData.glassCatalogs` |
| Clear semi-diam. margin | `prd.clear_semi_diam_margin` | `metaData.margin` |
| Fields | `prd.fields` | `metaData.fields` |
| Wavelengths | `prd.waves` | `metaData.wavelengths` |

### Per-surface data summary (all surfaces)

| Zemax column | Attribute | Notes |
|---|---|---|
| Surface type | `surf.TYPE` | See surface types below |
| Curvature (1/R) | `surf.CURV` | |
| Thickness / distance | `surf.DISZ` | |
| Glass name | `surf.GLAS` | with refractive index appended after parsing |
| Semi-diameter | `surf.DIAM` | used as obscuration radius |
| Conic constant | `surf.CONI` | |
| Comment | `surf.COMM` | used as `name` in YAML output |

### Per-surface coordinate system

Extracted from the rotation matrix / offset / tilt block in the prescription:

| Quantity | YAML key | Notes |
|---|---|---|
| X position | `coordSys.x` | metres |
| Y position | `coordSys.y` | metres |
| Z position | `coordSys.z` | metres |
| Rotation about X | `coordSys.rotX` | radians |
| Rotation about Y | `coordSys.rotY` | radians |
| Rotation about Z | `coordSys.rotZ` | radians |

### Surface shapes (geometry)

The following Zemax surface types are recognised and converted:

| Zemax `TYPE` | Condition | Batoid shape | Parameters written |
|---|---|---|---|
| Any | `CURV = 0` | `Plane` | — |
| `STANDARD` | conic = 0 | `Sphere` | `R` |
| `STANDARD` | conic = −1 | `Paraboloid` | `R` |
| `STANDARD` | other conic | `Quadric` | `R`, `conic` |
| `EVENASPH` | — | `Asphere` | `R`, `conic`, `coefs` [α₁ … α₈] (units converted to m⁻¹, m⁻³, …) |
| `BICONICX` | — | `Biconic` | `Ry`, `Rx`, `ky`, `kx` |
| `SZERNSAG` | — | `Sum` of `Asphere` + `Zernike` | asphere params + Zernike coefficients |
| `XPOLYNOM` | — | `Sum` of base + `XPolynom` | polynomial coefficients, normalisation radius |
| `BINARY_2` | — | `Asphere` + separate `OPDScreen` | asphere coefs + diffractive coefs (order, norm. radius, binary coefs) |
| `COORDBRK` | — | skipped (coordinate break handled silently) | — |

### Apertures / obscurations

All Zemax aperture types found in the **surface data detail** block are converted:

| Zemax aperture label | `ISAP` flag | Batoid obscuration | Parameters written |
|---|---|---|---|
| Circular Aperture (`CLAP`) | 1 (clear) | `ClearAnnulus` | `inner`, `outer`, `x`, `y` |
| Circular Aperture (`CLAP`) | 0 (obscuring) | `ObscAnnulus` | `inner`, `outer`, `x`, `y` |
| Elliptical Aperture (`ELAP`) | 1 (clear) | `ClearEllipse` | `semi_major`, `semi_minor`, `x`, `y` |
| Elliptical Aperture (`ELAP`) | 0 (obscuring) | `ObscEllipse` | `semi_major`, `semi_minor`, `x`, `y` |
| Rectangular Aperture (`SQAP`) | 1 (clear) | `ClearRectangle` | `width`, `height`, `x`, `y` |
| Rectangular Aperture (`SQAP`) | 0 (obscuring) | `ObscRectangle` | `width`, `height`, `x`, `y` |
| User Aperture (`USER`) | 1 (clear) | `ClearPolygon` | `xs`, `ys` (polygon vertex lists; last point — Zemax center point — is removed) |
| User Aperture (`USER`) | 0 (obscuring) | `ObscPolygon` | `xs`, `ys` (last point — Zemax center point — is removed) |
| (default, no aperture spec) | — | `ClearCircle` | `radius` (= semi-diameter), `x`, `y` |

Aperture decenters (`X- Decenter`, `Y- Decenter`) are read and applied as `x`, `y` offsets.

### Optical media

Each surface glass is looked up in the bundled AGF catalogs and converted to a Sellmeier medium.
Media are output with YAML anchors so identical glasses are referenced, not duplicated:

| Glass type | YAML representation | Parameters |
|---|---|---|
| Air / vacuum | `ConstMedium` anchored `&AIR` | `n: 1.0` |
| Named glass (catalog) | `SellmeierMedium` anchored `&<NAME>` | `B1, B2, B3, C1, C2, C3` |
| Custom index (numeric) | `ConstMedium` | `n: <value>` |

For the list of supported glass catalogs and individual glasses, see [Glass catalogs](#glass-catalogs) below.

### Surface element types in the output

Each surface in `wanted_surf_list` becomes one of:

| Batoid element type | Produced when |
|---|---|
| `Mirror` | `GLAS` starts with `"MIRROR"` (any case) |
| `RefractiveInterface` | `GLAS` is a named glass or numeric index |
| `RefractiveInterface` (air gap) | No `GLAS` entry on that surface |
| `OPDScreen` | `BINARY_2` surface (yielded *in addition* to the asphere base) |
| `Interface` | Entrance pupil stop surface (`stopSurface`) |
| `Detector` | Last surface (`IMA`) |

### Per-surface extra parameters

| Surface `TYPE` | `PARAM` fields extracted | Written as |
|---|---|---|
| `COORDBRK` | `PARM1`–`PARM5` (decenter X/Y, tilt X/Y/Z, order) | internal coordinate transformation |
| `EVENASPH` | `PARM1`–`PARM8` (α₁–α₈) | `Asphere.coefs` |
| `BICONICX` | `PARM1` (Rx), `PARM2` (kx) | `Biconic.Rx`, `.kx` |
| `SZERNSAG` | `PARM1`–`PARM8` (α₁–α₈) + `XDAT1`–`XDATN` (Zernike coefs) | `Sum` items |
| `XPOLYNOM` | `XDAT1` (max term), `XDAT2` (norm radius), `XDAT3`–`XDATN` (coefs) | `XPolynom` |
| `BINARY_2` | `PARM0` (order), `PARM1`–`PARM8` (α₁–α₈), `XDAT1`–`XDATN` (diffractive coefs) | `Asphere` + `OPDScreen` |

---

## Glass catalogs

The package ships with bundled `.agf` files covering the following manufacturers.
Individual glass names are not listed here due to their large number, but the AGF files can be
browsed directly in `src/zmx2yaml/AGF_files/`.

| Catalog dict | AGF file | Notes |
|---|---|---|
| `ARCHER` | `archer.agf` | |
| `ARTON` | `arton.agf` | |
| `BIREFRINGENT` | `birefringent.agf` | Calcite, MgF₂, Quartz, BBO, … |
| `CDGM` | `cdgm.agf` | H-QK, H-ZK, H-LAK, ZF, H-LAF series |
| `CORNING` | `corning.agf` | |
| `HERAEUS` | `heraeus.agf` | HOQ, Infrasil, Suprasil, Herasil |
| `HIKARI` | `hikari.agf` | J-BK7, J-LAK, J-SF, E-* series |
| `HOYA` | `hoya.agf` | FCD, TAF, FDS, TAFD, NBFD, BSC7, BAC |
| `INFRARED` | `infrared.agf` | Germanium, Silicon, ZnSe, CaF₂, Cleartran |
| `ISUZU` | `isuzu.agf` | |
| `LIEBETRAUT` | `liebetraut.agf` | Water, Glycerol, Toluene, Bromobenzene, … |
| `LIGHTPATH` | `lightpath.agf` | |
| `LZOS` | `lzos.agf` | LZ_BF*, LZ_TK*, LZ_F* series |
| `MISC` | `misc.agf` | Acrylic, CaF₂, PMMA, Silica, Vacuum, Seawater, Quartz |
| `NIKON` | `nikon.agf` | J-BK7, J-FK, J-SK, J-SF, J-BAF |
| `OHARA` | `ohara.agf` | S-BSL7, S-FSL5, S-LAH, S-TIH series |
| `RAD_HARD` | `rad_hard.agf` | Radiation-hardened variants |
| `RPO` | `rpo.agf` | |
| `SCHOTT` | `schott.agf` | N-BK7, N-SF, N-LAK, N-BAK, P-SK, Lithotec-CaF2 |
| `SUMITA` | `sumita.agf` | K-VC, K-PSFn series |
| `TOPAS` | `topas.agf` | TOPAS-5013, TOPAS-6013, TOPAS-8007 |
| `UMICORE` | `umicore.agf` | GASIR1, GASIR2, GE33, AMTIR-1 |
| `ZEON` | `zeon.agf` | Zeonex 480R, 330R |

The catalog to search is determined from the `Glass Catalogs:` line in the prescription header.
Sellmeier coefficients are cached across surfaces, so each glass is only looked up once per run.

---

## Unit handling

All length quantities are converted from the Zemax lens unit (typically Millimeters) to **metres**
in the output. Wavelengths are converted from µm to metres. Rotation angles are converted from
degrees (stored internally by Zemax from the tilt block) to **radians** in `coordSys`.

---

## Limitations / not yet supported

- Binary `.zmx` files (only text prescription exports are supported)
- Multi-configuration: `zmx2yaml` does not support multi-config prescription files. Export one prescription text file per configuration in Zemax OpticStudio, then run the script once per configuration to produce one YAML file per configuration. (Configuration data is parsed internally via `extract_multi_configurations()` but is not propagated to the YAML output.)
- Gradient-index surfaces (`GRINSUR`, `GRADIUM`, …)
- Holographic / diffractive surfaces other than `BINARY_2`
