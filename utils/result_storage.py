"""
Result Storage Utilities
=========================

Provides utilities for saving and loading experiment results:
- JSON format (human-readable, metadata)
- HDF5 format (large arrays, compressed)
- CSV format (tables, spreadsheet-compatible)
- Pickle format (full Python objects)
"""

import json
import pickle
import csv
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import numpy as np


try:
    import h5py
    HAS_HDF5 = True
except ImportError:
    HAS_HDF5 = False


class ResultStorage:
    """
    Manager for saving and loading experiment results.

    Supports multiple formats:
    - JSON: Metadata, parameters, small results
    - HDF5: Large arrays, trajectories (requires h5py)
    - CSV: Tables for spreadsheet analysis
    - Pickle: Full Python objects (not recommended for archival)
    """

    def __init__(self, results_dir: Union[str, Path]):
        """
        Initialize result storage.

        Args:
            results_dir: Directory for saving results
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def save_json(self, data: Dict[str, Any], filename: str):
        """
        Save data to JSON file.

        Args:
            data: Dictionary to save
            filename: Output filename (without path)
        """
        filepath = self.results_dir / filename
        if not filepath.suffix:
            filepath = filepath.with_suffix('.json')

        # Convert numpy arrays to lists
        data_serializable = self._make_json_serializable(data)

        with open(filepath, 'w') as f:
            json.dump(data_serializable, f, indent=2)

        return filepath

    def load_json(self, filename: str) -> Dict[str, Any]:
        """
        Load data from JSON file.

        Args:
            filename: Input filename

        Returns:
            Loaded dictionary
        """
        filepath = self.results_dir / filename
        if not filepath.suffix:
            filepath = filepath.with_suffix('.json')

        with open(filepath, 'r') as f:
            return json.load(f)

    def save_hdf5(self, data: Dict[str, Any], filename: str):
        """
        Save data to HDF5 file (for large arrays).

        Args:
            data: Dictionary with numpy arrays
            filename: Output filename

        Raises:
            ImportError: If h5py is not installed
        """
        if not HAS_HDF5:
            raise ImportError("h5py not installed. Install with: pip install h5py")

        filepath = self.results_dir / filename
        if not filepath.suffix:
            filepath = filepath.with_suffix('.h5')

        with h5py.File(filepath, 'w') as f:
            self._save_to_hdf5_group(f, data)

        return filepath

    def load_hdf5(self, filename: str) -> Dict[str, Any]:
        """
        Load data from HDF5 file.

        Args:
            filename: Input filename

        Returns:
            Dictionary with loaded arrays
        """
        if not HAS_HDF5:
            raise ImportError("h5py not installed. Install with: pip install h5py")

        filepath = self.results_dir / filename
        if not filepath.suffix:
            filepath = filepath.with_suffix('.h5')

        with h5py.File(filepath, 'r') as f:
            return self._load_from_hdf5_group(f)

    def save_csv(self, data: List[Dict[str, Any]], filename: str, headers: Optional[List[str]] = None):
        """
        Save tabular data to CSV file.

        Args:
            data: List of dictionaries (rows)
            filename: Output filename
            headers: Column headers (default: keys from first row)
        """
        if not data:
            raise ValueError("Cannot save empty data to CSV")

        filepath = self.results_dir / filename
        if not filepath.suffix:
            filepath = filepath.with_suffix('.csv')

        if headers is None:
            headers = list(data[0].keys())

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)

        return filepath

    def load_csv(self, filename: str) -> List[Dict[str, Any]]:
        """
        Load tabular data from CSV file.

        Args:
            filename: Input filename

        Returns:
            List of dictionaries (rows)
        """
        filepath = self.results_dir / filename
        if not filepath.suffix:
            filepath = filepath.with_suffix('.csv')

        with open(filepath, 'r', newline='') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def save_pickle(self, data: Any, filename: str):
        """
        Save arbitrary Python object to pickle file.

        Warning: Pickle is not recommended for long-term archival.

        Args:
            data: Object to save
            filename: Output filename
        """
        filepath = self.results_dir / filename
        if not filepath.suffix:
            filepath = filepath.with_suffix('.pkl')

        with open(filepath, 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

        return filepath

    def load_pickle(self, filename: str) -> Any:
        """
        Load object from pickle file.

        Args:
            filename: Input filename

        Returns:
            Loaded object
        """
        filepath = self.results_dir / filename
        if not filepath.suffix:
            filepath = filepath.with_suffix('.pkl')

        with open(filepath, 'rb') as f:
            return pickle.load(f)

    def _make_json_serializable(self, obj: Any) -> Any:
        """Recursively convert objects to JSON-serializable format."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, Path):
            return str(obj)
        else:
            return obj

    def _save_to_hdf5_group(self, group: 'h5py.Group', data: Dict[str, Any]):
        """Recursively save dictionary to HDF5 group."""
        for key, value in data.items():
            if isinstance(value, dict):
                subgroup = group.create_group(key)
                self._save_to_hdf5_group(subgroup, value)
            elif isinstance(value, np.ndarray):
                group.create_dataset(key, data=value, compression='gzip')
            elif isinstance(value, (list, tuple)) and len(value) > 0 and isinstance(value[0], np.ndarray):
                # List of arrays (e.g., x_blocks)
                subgroup = group.create_group(key)
                for i, arr in enumerate(value):
                    subgroup.create_dataset(f"item_{i}", data=arr, compression='gzip')
            elif isinstance(value, (int, float, str)):
                group.attrs[key] = value
            else:
                # Convert to JSON string for complex types
                group.attrs[key] = json.dumps(value, default=str)

    def _load_from_hdf5_group(self, group: 'h5py.Group') -> Dict[str, Any]:
        """Recursively load dictionary from HDF5 group."""
        result = {}

        # Load datasets
        for key in group.keys():
            item = group[key]
            if isinstance(item, h5py.Dataset):
                result[key] = item[()]
            elif isinstance(item, h5py.Group):
                # Check if it's a list of arrays (has item_0, item_1, ...)
                if all(k.startswith('item_') for k in item.keys()):
                    result[key] = [item[k][()] for k in sorted(item.keys())]
                else:
                    result[key] = self._load_from_hdf5_group(item)

        # Load attributes
        for key, value in group.attrs.items():
            if isinstance(value, str) and (value.startswith('[') or value.startswith('{')):
                try:
                    result[key] = json.loads(value)
                except:
                    result[key] = value
            else:
                result[key] = value

        return result


def save_experiment_results(
    experiment_name: str,
    category: str,
    results: Dict[str, Any],
    save_formats: List[str] = ['json', 'hdf5'],
):
    """
    Convenience function to save experiment results in multiple formats.

    Args:
        experiment_name: Name of experiment (e.g., "I.1_envelope_verification")
        category: Category (e.g., "I")
        results: Results dictionary
        save_formats: List of formats to save ('json', 'hdf5', 'pickle')

    Returns:
        Dictionary mapping format to saved filepath
    """
    results_dir = Path(__file__).parent.parent / "results" / f"category_{category}"
    storage = ResultStorage(results_dir)

    saved_files = {}

    if 'json' in save_formats:
        filepath = storage.save_json(results, experiment_name)
        saved_files['json'] = filepath
        print(f"Saved JSON: {filepath}")

    if 'hdf5' in save_formats and HAS_HDF5:
        filepath = storage.save_hdf5(results, experiment_name)
        saved_files['hdf5'] = filepath
        print(f"Saved HDF5: {filepath}")

    if 'pickle' in save_formats:
        filepath = storage.save_pickle(results, experiment_name)
        saved_files['pickle'] = filepath
        print(f"Saved Pickle: {filepath}")

    return saved_files


def load_experiment_results(
    experiment_name: str,
    category: str,
    format: str = 'json',
) -> Dict[str, Any]:
    """
    Convenience function to load experiment results.

    Args:
        experiment_name: Name of experiment
        category: Category
        format: Format to load ('json', 'hdf5', 'pickle')

    Returns:
        Loaded results dictionary
    """
    results_dir = Path(__file__).parent.parent / "results" / f"category_{category}"
    storage = ResultStorage(results_dir)

    if format == 'json':
        return storage.load_json(experiment_name)
    elif format == 'hdf5':
        return storage.load_hdf5(experiment_name)
    elif format == 'pickle':
        return storage.load_pickle(experiment_name)
    else:
        raise ValueError(f"Unknown format: {format}")
