import os
import yaml
from pathlib import Path
from typing import Dict, List

from .models import FrameworkSchema

class FrameworkLoader:
    def __init__(self, data_dir: str = "data/frameworks"):
        self.data_dir = Path(data_dir)
        self.frameworks: Dict[str, FrameworkSchema] = {}

    def load_all(self) -> Dict[str, FrameworkSchema]:
        """
        Loads all framework YAML files from the data directory.
        Validates them against the Pydantic schema and returns a dictionary
        mapping framework ID to the loaded FrameworkSchema object.
        """
        self.frameworks.clear()
        
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

        for file_path in self.data_dir.glob("*.yaml"):
            # Skip schema definition file
            if file_path.name == "schema.yaml":
                continue
                
            try:
                framework = self._load_file(file_path)
                if framework.id in self.frameworks:
                    print(f"Warning: Duplicate framework ID '{framework.id}' found in {file_path}. Overwriting.")
                self.frameworks[framework.id] = framework
            except Exception as e:
                print(f"Error loading {file_path.name}: {str(e)}")

        return self.frameworks

    def _load_file(self, file_path: Path) -> FrameworkSchema:
        """
        Loads and validates a single YAML file.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        if not data:
            raise ValueError(f"File {file_path} is empty or invalid YAML")
            
        return FrameworkSchema.model_validate(data)

    def get_framework(self, framework_id: str) -> FrameworkSchema:
        """Get a framework by its ID."""
        if framework_id not in self.frameworks:
            raise KeyError(f"Framework '{framework_id}' not loaded")
        return self.frameworks[framework_id]

    def get_by_category(self, category: str) -> List[FrameworkSchema]:
        """Get all frameworks matching a specific category."""
        return [f for f in self.frameworks.values() if f.category == category]
        
    def get_by_genome_dimension(self, dimension_key: str) -> List[FrameworkSchema]:
        """Get all frameworks that provide a specific genome dimension."""
        return [f for f in self.frameworks.values() if f.genome_dimension.key == dimension_key]

if __name__ == "__main__":
    # Test script to verify loading
    import sys
    
    # Allow running from project root or src/data
    base_dir = "." if Path("data/frameworks").exists() else "../.."
    data_dir = os.path.join(base_dir, "data/frameworks")
    
    loader = FrameworkLoader(data_dir=data_dir)
    try:
        frameworks = loader.load_all()
        print(f"Successfully loaded {len(frameworks)} frameworks:")
        for fw_id, fw in frameworks.items():
            print(f"  - {fw.name} ({fw.category})")
            
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)
