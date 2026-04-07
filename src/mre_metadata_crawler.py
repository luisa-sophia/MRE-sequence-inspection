from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import mre_metadata
from dataclasses import asdict


@dataclass(frozen=True)
class CrawlPaths:
    """Filesystem locations and templates needed for one scanner crawl."""
    label: str
    dicom_root: Path
    output_tsv_path: Path
    folder_pattern_template: str


class MREMetadataCrawler:
    """Stateful wrapper around MRE metadata extraction for one scanner setup."""

    def __init__(self, crawl_paths: CrawlPaths, ignore_hidden: bool = True):
        self.paths = crawl_paths
        self.ignore_hidden = ignore_hidden

    @property
    def label(self) -> str:
        """Return the human-readable scanner label."""
        return self.paths.label

    def load_existing_summary(self) -> pd.DataFrame:
        """Load the current summary TSV for this crawler."""
        return mre_metadata.load_existing_summary(self.paths.output_tsv_path)

    def list_available_subjects(self) -> list[str]:
        """List all subject folders currently available under the crawler's DICOM root."""
        return mre_metadata.list_available_subjects(
            self.paths.dicom_root,
            ignore_hidden=self.ignore_hidden,
        )

    def get_missing_subjects(self) -> list[str]:
        """List subject folders that are not yet present in the summary TSV."""
        return mre_metadata.get_missing_subjects(
            self.paths.output_tsv_path,
            self.paths.dicom_root,
            ignore_hidden=self.ignore_hidden,
        )

    def resolve_subjects(
        self,
        subject_override: list[str] | None = None,
        force_all_subjects: bool = False,
    ) -> list[str]:
        """Resolve which subjects this run should process."""
        if force_all_subjects:
            return self.list_available_subjects()
        if subject_override is not None:
            return sorted(subject_override)
        return self.get_missing_subjects()
    
    def print_setup(self):
        """Print the crawler configuration for notebook inspection."""
        print("=== MRE Metadata Crawler Setup ===")
        for key, value in asdict(self.paths).items():
            print(f"{key:18}: {value}")
        print(f"{'ignore_hidden':18}: {self.ignore_hidden}")


    def update_summary(
        self,
        subject_override: list[str] | None = None,
        verbose: bool = False,
        dry_run: bool = False,
        append_if_exists: bool = True,
        overwrite: bool = False,
        force_all_subjects: bool = False,
    ):
        """Run metadata extraction and update the summary TSV.

        By default, only subjects missing from the current summary TSV are
        processed. Set `force_all_subjects=True` to re-scan the full DICOM root.
        """
        subject_list = self.resolve_subjects(
            subject_override=subject_override,
            force_all_subjects=force_all_subjects,
        )

        if not subject_list:
            print(f"{self.label}: all subjects already summarized.")
            return None, None, self.load_existing_summary()

        print(f"{self.label}: processing {len(subject_list)} subject(s)")
        for subject in subject_list:
            print("-", subject)

        return mre_metadata.update_summary_tsv(
            self.paths.folder_pattern_template,
            self.paths.output_tsv_path,
            subject_list=subject_list,
            ignore_hidden=self.ignore_hidden,
            append_if_exists=append_if_exists,
            overwrite=overwrite,
            dry_run=dry_run,
            verbose=verbose,
            force_all_subjects=force_all_subjects,
        )
