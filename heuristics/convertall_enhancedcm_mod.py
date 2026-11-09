from __future__ import annotations

import logging
from typing import Optional

from heudiconv.utils import SeqInfo

lgr = logging.getLogger("heudiconv")


def create_key(
    template: Optional[str],
    outtype: tuple[str, ...] = ("nii.gz",),
    annotation_classes: None = None,
) -> tuple[str, tuple[str, ...], None]:
    if template is None or not template:
        raise ValueError("Template must be a valid format string")
    return (template, outtype, annotation_classes)


def infotodict(
    seqinfo: list[SeqInfo],
) -> dict[tuple[str, tuple[str, ...], None], list[str]]:
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """

    data = create_key("run{item:03d}")
    info: dict[tuple[str, tuple[str, ...], None], list[str]] = {data: []}

    for s in seqinfo:
        """
        The namedtuple `s` contains the following fields:

        * total_files_till_now
        * example_dcm_file
        * series_id
        * dcm_dir_name
        * unspecified2
        * unspecified3
        * dim1
        * dim2
        * dim3
        * dim4
        * TR
        * TE
        * protocol_name
        * is_motion_corrected
        * is_derived
        * patient_id
        * study_description
        * referring_physician_name
        * series_description
        * image_type
        """

        info[data].append(s.series_id)
    return info


#added custom field for incapability of heudiconv to extract TR and TE from enhanced DICOMs
def custom_seqinfo(series_files, wrapper, **kw):
    import pydicom
    ds = pydicom.dcmread(series_files[0])
    #only necessary if enhanced format, otherwise TR and TE are already in the SeqInfo
    if ds[0x008,0x0016].value == '1.2.840.10008.5.1.4.1.1.4.1':
        TR, TE = None, None
        try:
            TR = float(ds[0x5200,0x9229].value[0][0x0018,0x9112].value[0][0x0018,0x0080].value) / 1000 #TR in seconds (consistent with heudiconv)
        except Exception:
            pass
        try:
            TE = float(ds[0x5200,0x9230].value[0][0x0018,0x9114].value[0][0x0018,0x9082].value) # TE in ms yes this stays in ms (stupid but consistent with heudiconv)
        except Exception:
            pass
    
        return (("TR", TR), ("TE", TE))
