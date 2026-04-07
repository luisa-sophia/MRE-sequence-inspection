from pathlib import Path
import glob
import os
import re

import numpy as np
import pandas as pd
import pydicom


SUMMARY_KEY_COLUMNS = ["SubjectName", "PatientID", "Date", "SeriesNumberPhase"]
SUMMARY_SORT_COLUMNS = ["Date", "PatientID", "SeriesNumberPhase"]
SUMMARY_OUTPUT_COLUMNS = [
    "SubjectName",
    "PatientID",
    "Date",
    "SeriesNumberPhase",
    "Resolution",
    "TR",
    "TE",
    "SeriesDescription",
    "InPlanePhaseEncodingDirection",
    "ScanOrder",
    "freqIndices",
    "freqs_Hz",
    "timeStepIndices",
    "dirIndices",
    "megVector",
    "num_files",
]


def format_meg_vector(vectors):
    """Format one or more motion-encoding vectors for TSV output."""
    if isinstance(vectors, str):
        return vectors
    if isinstance(vectors, tuple) and len(vectors) == 3:
        vectors = [vectors]
    return "[" + "; ".join("({:.3f}, {:.3f}, {:.3f})".format(*vec) for vec in vectors) + "]"



def _is_mre_phase_slice(file_path: str) -> bool:
    """Return True if a DICOM file appears to be an MRE phase image."""
    try:
        ds = pydicom.dcmread(
            file_path,
            stop_before_pixels=True,
            specific_tags=["ImageComments"],
        )
        image_comments = ds.get("ImageComments")
        return isinstance(image_comments, str) and image_comments.startswith("MRE:")
    except Exception:
        return False




def _get_slice_plane(dcm):
    """Infer acquisition plane from the DICOM orientation vectors."""
    image_ori_patient = np.array(dcm.ImageOrientationPatient, dtype=float)
    row = image_ori_patient[:3]
    col = image_ori_patient[3:]
    normal = np.cross(row, col)
    axis = np.argmax(np.abs(normal))
    return ["sagittal", "coronal", "axial"][axis]



def _list_subject_dirs(dicom_root: str | Path, ignore_hidden: bool = True) -> list[str]:
    """List subject directories under a DICOM root."""
    entries = [entry.name for entry in Path(dicom_root).iterdir() if entry.is_dir()]
    if ignore_hidden:
        entries = [entry for entry in entries if not entry.startswith(".")]
    return sorted(entries)



def _split_folder_pattern_template(folder_pattern_template: str) -> tuple[str, str, str]:
    """Split a folder template into root, sequence glob, and file pattern."""
    if "{subject}" not in folder_pattern_template:
        raise ValueError("The given template does not contain the {subject} placeholder.")
    if "*." not in folder_pattern_template:
        raise ValueError("Template must include a file pattern like '*.dcm'.")

    dicom_root = folder_pattern_template.split("{subject}")[0]
    sequence_pattern_template, file_ext = folder_pattern_template.split("*.")
    file_pattern = f"*.{file_ext.strip()}"
    return dicom_root, sequence_pattern_template, file_pattern


_split_pattern_template = _split_folder_pattern_template



def _extract_sequence_metadata(seq_dir: str, file_pattern: str, subject_name: str, ignore_hidden: bool, verbose: bool) -> list[dict]:
    """Extract metadata rows from a single sequence directory if it contains MRE phase data."""
    file_paths = glob.glob(os.path.join(seq_dir, file_pattern), include_hidden=not ignore_hidden)
    if not file_paths:
        if verbose:
            print(f"WARNING: No files found for sequence directory '{seq_dir}', subject '{subject_name}'.")
        return []

    if not _is_mre_phase_slice(file_paths[0]):
        if verbose:
            print(f"NO, MRE metadata in '{seq_dir}', skipping folder...")
        return []

    metadata_rows = []
    printed_note = False
    for file_path in file_paths:
        mre_info = try_extract_metadata_from_mre_dicom(file_path, custom_subject_name=subject_name)
        if mre_info is None:
            continue
        metadata_rows.append(mre_info)
        if verbose and not printed_note:
            print(f"YES, MRE metadata found in '{seq_dir}', processing files...")
            printed_note = True
    return metadata_rows



def extract_MRE_seq_info(folder_pattern_template, subject_list=None, ignore_hidden=True, verbose=True):
    """Scan subjects for MRE phase series and return summary and per-file metadata tables.

    Passing `subject_list=None` or `subject_list=[]` triggers a full crawl of all
    subjects under the DICOM root encoded in `folder_pattern_template`.
    """
    dicom_root, sequence_pattern_template, file_pattern = _split_folder_pattern_template(folder_pattern_template)

    sub_dirs = _list_subject_dirs(dicom_root, ignore_hidden=ignore_hidden) if not subject_list else sorted(subject_list)
    mre_info_list = []

    for si, sub_dir in enumerate(sub_dirs, start=1):
        if verbose:
            print(f"\nProcessing subject: {sub_dir} ({si}/{len(sub_dirs)})")
        sequence_glob = sequence_pattern_template.format(subject=sub_dir)
        sequence_dirs = glob.glob(sequence_glob, recursive=True, include_hidden=not ignore_hidden)

        if not sequence_dirs:
            if verbose:
                print(f"WARNING: No sequence directories found for subject '{sub_dir}' with pattern '{sequence_glob}'.")
            continue

        for seq_dir in sequence_dirs:
            mre_info_list.extend(
                _extract_sequence_metadata(
                    seq_dir=seq_dir,
                    file_pattern=file_pattern,
                    subject_name=sub_dir,
                    ignore_hidden=ignore_hidden,
                    verbose=verbose,
                )
            )

    df_full = pd.DataFrame()
    df_summary = pd.DataFrame()
    subs_with_mre = set()

    if mre_info_list:
        df_full = pd.DataFrame(mre_info_list).sort_values(by="SOPInstanceUID").reset_index(drop=True)
        df_summary = create_subject_MRE_overview_table(df_full)
        subs_with_mre = set(df_summary["SubjectName"].values)
        cols_to_keep = [col for col in SUMMARY_OUTPUT_COLUMNS if col in df_summary.columns]
        df_summary = df_summary[cols_to_keep]
        sort_cols = [col for col in SUMMARY_SORT_COLUMNS if col in df_summary.columns]
        if sort_cols:
            df_summary = df_summary.sort_values(by=sort_cols).reset_index(drop=True)

    non_mre_subs = set(sub_dirs) - subs_with_mre
    if non_mre_subs:
        print(
            "\n===============================================================================\n"
            "WARNING, Found no sequences with MRE ImageComment for the following subjects:\n",
            ",".join(sorted(non_mre_subs)),
            "\n===============================================================================\n",
        )

    return df_summary, df_full



def try_extract_metadata_from_mre_dicom(file_path, custom_subject_name=None):
    """Parse one DICOM file and return extracted MRE metadata, or `None` if it is not usable."""
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)
        image_comment = ds.get("ImageComments")
        if not (image_comment and image_comment.startswith("MRE:")):
            return None

        image_comment_data = parse_MRE_tag(ds, convert_arrays_to_list=True)
        pxlspacing = ds.get("PixelSpacing", [-1, -1])
        z_spacing = ds.get("SpacingBetweenSlices", -1)
        zooms = tuple(round(float(x), 3) for x in np.hstack((pxlspacing, z_spacing)))
        date = ds.get("AcquisitionDate")
        date = f"{date[:4]}-{date[4:6]}-{date[-2:]}" if date else None
        relative_filepath = os.path.splitdrive(file_path)[1]

        metadata = {
            "PatientID": str(ds.get("PatientName", "N/A")),
            "SubjectName": custom_subject_name if custom_subject_name else str(ds.get("PatientID", "N/A")),
            "SeriesNumberPhase": ds.get("SeriesNumber", "N/A"),
            "Path": relative_filepath,
            "SOPInstanceUID": ds.get("SOPInstanceUID", "N/A"),
            "Resolution": str(zooms),
            "TR": ds.get("RepetitionTime", "N/A"),
            "TE": ds.get("EchoTime", "N/A"),
            "SeriesDescription": ds.get("SeriesDescription"),
            "InPlanePhaseEncodingDirection": ds.get("InPlanePhaseEncodingDirection", "N/A"),
            "ImageType": str(ds.get("ImageType", "N/A")),
            "Date": date,
            "ScanOrder": _get_slice_plane(ds),
        }
        metadata.update(image_comment_data)
        return metadata
    except Exception as e:
        print(f"Error processing {file_path}: {e}\n --> Skipping this file.")
        return None



def create_subject_MRE_overview_table(mre_info_df):
    """Collapse per-file metadata into one summary row per MRE phase series."""
    mre_info_df = mre_info_df.copy()
    mre_info_df["megVector"] = mre_info_df["megVector"].apply(lambda v: tuple(v) if isinstance(v, list) else v)
    grouped = mre_info_df.groupby(["PatientID", "Date", "SeriesNumberPhase"], as_index=False).agg(
        num_files=("SOPInstanceUID", "size"),
        **{col: (col, "unique") for col in mre_info_df.columns if col not in ["PatientID", "Date", "SeriesNumberPhase"]},
    ).reset_index(drop=True)
    grouped["freqs_Hz"] = grouped["freqs_Hz"].apply(lambda values: [round(float(freq), 2) for freq in values])
    return collapse_unique_columns(grouped)



def collapse_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten list-like columns that only contain one unique value per row."""
    df = df.copy()
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (list, tuple, np.ndarray))).all():
            lengths = df[col].apply(len)
            if (lengths == 1).all():
                df[col] = df[col].apply(lambda x: x[0])
    return df



def load_existing_summary(tsv_path: str | Path) -> pd.DataFrame:
    """Load an existing metadata summary TSV if it exists."""
    tsv_path = Path(tsv_path)
    if not tsv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(tsv_path, sep="\t")



def get_missing_subjects(tsv_path: str | Path, dicom_root: str | Path, ignore_hidden: bool = True) -> list[str]:
    """Return subject folders not yet present in the summary TSV."""
    existing_subjects = _list_subject_dirs(dicom_root, ignore_hidden=ignore_hidden)
    existing_summary = load_existing_summary(tsv_path)
    if existing_summary.empty:
        return existing_subjects
    processed_subjects = set(existing_summary["SubjectName"].astype(str))
    return sorted(set(existing_subjects) - processed_subjects)



def append_summary_rows(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Append new rows to an existing summary and de-duplicate by key columns."""
    if existing_df.empty:
        return new_df.copy()
    if new_df.empty:
        return existing_df.copy()

    combined = pd.concat([existing_df, new_df], ignore_index=True)
    dedupe_cols = [col for col in SUMMARY_KEY_COLUMNS if col in combined.columns]
    if dedupe_cols:
        combined = combined.drop_duplicates(subset=dedupe_cols, keep="last")
    sort_cols = [col for col in SUMMARY_SORT_COLUMNS if col in combined.columns]
    if sort_cols:
        combined = combined.sort_values(by=sort_cols).reset_index(drop=True)
    return combined



def list_available_subjects(dicom_root: str | Path, ignore_hidden: bool = True) -> list[str]:
    """Return all subject folders available under the given DICOM root."""
    return _list_subject_dirs(dicom_root, ignore_hidden=ignore_hidden)



def update_summary_tsv(
    folder_pattern_template: str,
    output_tsv_path: str | Path,
    subject_list: list[str] | None = None,
    ignore_hidden: bool = True,
    append_if_exists: bool = True,
    overwrite: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    force_all_subjects: bool = False,
):
    """Extract metadata and update the summary TSV.

    Parameters
    ----------
    subject_list:
        Explicit subjects to process. If `None`, the caller decides the scope.
    force_all_subjects:
        If `True`, ignore `subject_list` and re-scan all subjects found under the
        DICOM root encoded in `folder_pattern_template`.
    """
    requested_subjects = [] if force_all_subjects else subject_list

    summary_df, detailed_df = extract_MRE_seq_info(
        folder_pattern_template,
        subject_list=requested_subjects or [],
        ignore_hidden=ignore_hidden,
        verbose=verbose,
    )

    summary_to_write = summary_df.copy()
    if "megVector" in summary_to_write.columns:
        summary_to_write["megVector"] = summary_to_write["megVector"].apply(format_meg_vector)

    output_tsv_path = Path(output_tsv_path)
    if append_if_exists and output_tsv_path.exists() and not overwrite:
        existing_summary = load_existing_summary(output_tsv_path)
        summary_to_write = append_summary_rows(existing_summary, summary_to_write)

    if dry_run:
        print(f"Dry run activated. Would save to {output_tsv_path}")
    else:
        summary_to_write.to_csv(output_tsv_path, sep="\t", index=False)
        print(f"Wrote file to '{output_tsv_path}'")

    return summary_df, detailed_df, summary_to_write



def parse_MRE_tag(metadata_dict, convert_arrays_to_list=True, flatten_meg_vector=True):
    """Extract MRE-specific fields from the Siemens `ImageComments` tag."""
    extracted_info = {}

    if 'ImageComments' not in metadata_dict:
        return extracted_info

    tag = metadata_dict.ImageComments

    pattern = r'(\s|^|\])(fI|F )\[{0,1}(?P<freqIndices>\d+)\]{0,1}'
    ret = re.search(pattern, tag, flags=re.IGNORECASE)
    extracted_info['freqIndices'] = int(ret.group('freqIndices')) if ret else -1

    pattern = r'(\s|^|\])dI\[(?P<dirIndices>\d+)\]'
    ret = re.search(pattern, tag, flags=re.IGNORECASE)
    extracted_info['dirIndices'] = int(ret.group('dirIndices')) if ret else -1

    pattern = r'\({0,1}(?P<encDir>(slice|read|phase|readout))\){0,1}'
    ret = re.search(pattern, tag, flags=re.IGNORECASE)
    if ret:
        encDir = ret.group('encDir')
        if encDir != tag:
            megOpt = ['read', 'phase', 'slice']
            try:
                extracted_info['megIndices'] = next(i for i, opt in enumerate(megOpt) if opt.lower() == encDir.lower())
            except StopIteration:
                extracted_info['megIndices'] = -1
    else:
        extracted_info['megIndices'] = -1

    pattern = r'(\s|^|\])az\[(?P<azimuths>\d+)\]po\[(?P<polars>\d+)\]'
    ret = re.search(pattern, tag, flags=re.IGNORECASE)
    if ret:
        if not metadata_dict.get('enhanced', False):
            extracted_info['SliceLocation'] = metadata_dict.get('SliceLocation', None)

        iop = metadata_dict.get('ImageOrientationPatient')
        if isinstance(iop, list):
            iop = np.array(iop)
            extracted_info['ImageOrientationPatient'] = iop

        extracted_info['azimuth'] = float(ret.group('azimuths'))
        extracted_info['polar'] = float(ret.group('polars'))

        cubeOrientation = np.zeros((3, 3))
        iop = metadata_dict['ImageOrientationPatient']
        cubeOrientation[:, 0] = iop[:3] / np.linalg.norm(iop[:3])
        cubeOrientation[:, 1] = iop[3:6] / np.linalg.norm(iop[3:6])
        cubeOrientation[:, 2] = np.cross(cubeOrientation[:, 0], cubeOrientation[:, 1])

        scannerSystemMatrix = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
        az = np.deg2rad(extracted_info['azimuth'])
        pol = np.deg2rad(extracted_info['polar'])
        dir_vec = np.zeros((3, 1))
        dir_vec[0, 0] = np.sin(pol) * np.cos(az)
        dir_vec[1, 0] = np.sin(pol) * np.sin(az)
        dir_vec[2, 0] = np.cos(pol)

        megVector = cubeOrientation.T @ scannerSystemMatrix @ dir_vec
        extracted_info['megVector'] = megVector
        resVector = np.eye(3) @ megVector
        absRes = np.abs(resVector)
        primary_idx = np.argmax(absRes)
        extracted_info['megIndices'] = primary_idx
        extracted_info['conjMeg'] = False
        if resVector[primary_idx] < 0:
            extracted_info['megVector'] = -extracted_info['megVector']
            extracted_info['conjMeg'] = True
        if flatten_meg_vector:
            extracted_info['megVector'] = extracted_info['megVector'].flatten().tolist()
        extracted_info['megIndices'] = int(extracted_info['megIndices'])
    else:
        extracted_info['conjMeg'] = False
        extracted_info['azimuth'] = None
        extracted_info['polar'] = None

    pattern = r'(\s|^|\])(tI|TS)(\[|\s)(?P<timeStepIndices>\d+)(\]|\s)'
    ret = re.search(pattern, tag, flags=re.IGNORECASE)
    extracted_info['timeStepIndices'] = int(ret.group('timeStepIndices')) if ret else -1

    pattern = r'(\s|^|\])(VP|VR)\[(?P<mechCycleTimes_us>\d+)\]'
    ret = re.search(pattern, tag, flags=re.IGNORECASE)
    if ret:
        extracted_info['mechCycleTimes_us'] = float(ret.group('mechCycleTimes_us'))
        extracted_info['freqs_Hz'] = 1e6 / extracted_info['mechCycleTimes_us']
    else:
        extracted_info['mechCycleTimes_us'] = 0
        extracted_info['freqs_Hz'] = 0

    if convert_arrays_to_list:
        for key, value in extracted_info.items():
            if isinstance(value, np.ndarray):
                extracted_info[key] = value.tolist()

    return extracted_info
