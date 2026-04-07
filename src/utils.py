from pathlib import Path
import os
import glob
import pandas as pd
import pydicom

def combine_paths(*segments: str, check_if_exists: bool = True) -> str:
    """
    Join multiple path segments into a single path.

    Rules:
    - At most one absolute path is allowed.
    - If present, the absolute path must be the first segment.
    - All other segments must be relative.
    """
    if not segments:
        raise ValueError("No path segments provided")

    paths = [Path(seg) for seg in segments]

    absolute_indices = [i for i, p in enumerate(paths) if p.is_absolute()]

    if len(absolute_indices) > 1 or (absolute_indices and absolute_indices[0] != 0):
        bad = [str(segments[i]) for i in absolute_indices]
        raise ValueError(
            f"Absolute paths are only allowed as the first segment. "
            f"Found: {bad}"
        )

    combined = paths[0]
    for p in paths[1:]:
        combined /= p

    combined = combined.resolve()

    if check_if_exists and not combined.exists():
        raise ValueError(
            f"Generated combined path '{combined}' does not exist. "
            f"Segments: {segments}"
        )

    return str(combined)


def find_root_with_marker(start: Path, marker: str) -> Path:
    for p in [start] + list(start.parents):
        if (p / marker).exists():
            return p
    raise FileNotFoundError(f"Marker'{marker}' indicating root level of drive not found.")

def get_ID_from_tsvpath(path):
    return os.path.normpath(path).split("info")[0].split(os.sep)[-2]


def extract_subject_foldername_and_patientid(pattern_template, ignore_hidden = True, folders_to_ignore = []):
    """
    Extract folder names and dicom patient names from DICOM directories.
    Automatically assumes the dicom root to be the part of the pattern before '{subject}' placeholder

    Args:
        pattern_template (str): path pattern to dicom files, must have {subject} placeholder. Example: 'A:\\MR_Data\\Raw\\7T_Terra\\{subject}\\SCANS\\*\\DICOM\\*.dcm'
        ignore_hidden (bool): Whether to ignore hidden folders.
        folders_to_ignore (list): Folder name substrings to exclude.

    Returns:
        pandas.DataFrame: DataFrame with columns 'foldername' and 'patient_name'.
        
    Raises:
        ValueError: If '{subject}' is not found in the pattern_template.
        
    """
    
    if "{subject}" not in pattern_template:
        raise ValueError("The given template does not contain the {subject} placeholder. Please specify with placeholder.")
    
    dicom_root = pattern_template.split("{subject}")[0]
    
    sub_dirs = os.listdir(dicom_root)
    if ignore_hidden:
        sub_dirs[:] = [d for d in sub_dirs if d[0] != '.']

    if folders_to_ignore:
        sub_dirs[:] = [d for d in sub_dirs if all(foldername not in d for foldername in folders_to_ignore)]

    subject_names = list()
    for sub_dir in sub_dirs:
        current_pattern_template = pattern_template.format(subject = sub_dir)
        # cur_root = os.path.join(dicom_root_path, sub_dir)
        iterator = glob.iglob(current_pattern_template, root_dir = dicom_root, recursive = True, include_hidden=ignore_hidden)
        first_match = next(iterator, None)
        if first_match is None:
            print(f"Skipping folder '{sub_dir}': No match found for regex '{current_pattern_template}' . Check folder hierarchy.")
            continue
        else:
            patient_name = str(pydicom.dcmread(os.path.join(dicom_root, first_match)).PatientName)
            
            # patient_id = str(pydicom.dcmread(os.path.join(cur_root, first_match)).PatientID)
            subject_info = {"foldername": sub_dir, "patient_name": patient_name}
            subject_names.append(subject_info)
    
    return pd.DataFrame(subject_names)

def write_df_as_tsv(df, out_path, overwrite = True):
    if not overwrite and os.path.exists(out_path):
        raise ValueError(f"File already exists at '{out_path}'")
    df.to_csv(out_path, sep = '\t', index = False)
    print(f"Wrote file to '{out_path}'")