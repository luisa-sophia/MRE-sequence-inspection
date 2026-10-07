import json
from dataclasses import dataclass
from pathlib import Path

from . import utils

DRIVE_ROOT_MARKER = ".drive_root.txt"


@dataclass(frozen=True)
class ScannerPaths:
    """Absolute paths for one scanner, resolved against the drive root."""
    label: str
    dicom_root: str
    output_root: str
    folder_template: str  # {dicom_root} filled in, {subject} stays as placeholder


@dataclass(frozen=True)
class Config:
    root: str
    scanners: dict[str, ScannerPaths]
    dicominfo_tsv_name: str
    metadata_summary_tsv_name: str
    modality_patterns: dict[str, list[str]]

    def show(self):
        """Print the resolved configuration for notebook inspection."""
        print(f"=== Config (drive root: '{self.root}') ===")
        for scanner in self.scanners.values():
            print(f"[{scanner.label}]")
            print(f"  {'dicom_root':16}: {scanner.dicom_root}")
            print(f"  {'output_root':16}: {scanner.output_root}")
            print(f"  {'folder_template':16}: {scanner.folder_template}")
        print(f"{'dicominfo_tsv_name':26}: {self.dicominfo_tsv_name}")
        print(f"{'metadata_summary_tsv_name':26}: {self.metadata_summary_tsv_name}")
        print("modality_patterns:")
        for modality, patterns in self.modality_patterns.items():
            print(f"  {modality:8}: {patterns}")


def load_config(config_path: str | Path = "CONFIG_FILE.json", start: str | Path | None = None) -> Config:
    """
    Load the config json and resolve all relative paths against the drive root.

    The drive root is the first folder (going upwards from `start`, default: cwd)
    that contains the marker file '.drive_root.txt'.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    root = utils.find_root_with_marker(Path(start or Path.cwd()), DRIVE_ROOT_MARKER)

    scanners = {}
    for label, s in cfg["SCANNERS"].items():
        dicom_root = utils.combine_paths(root, s["RELATIVE_DICOM_ROOT"])
        scanners[label] = ScannerPaths(
            label=label,
            dicom_root=dicom_root,
            output_root=utils.combine_paths(root, s["RELATIVE_OUTPUT_DIR_ROOT"], check_if_exists=False),
            folder_template=s["FOLDER_TEMPLATE"].format(dicom_root=dicom_root, subject="{subject}"),
        )

    return Config(
        root=str(root),
        scanners=scanners,
        dicominfo_tsv_name=cfg["DICOMINFO_TSV_NAME"],
        metadata_summary_tsv_name=cfg["METADATA_SUMMARY_TSV_NAME"],
        modality_patterns=cfg["MODALITY_SEQUENCE_IDENTIFIER_PATTERNS"],
    )
