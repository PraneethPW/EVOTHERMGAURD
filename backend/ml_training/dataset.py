"""Manifest dataset contract: rgb_path, thermal_path, ambient_temperature, humidity, weather, season, time_of_day, label."""
import pandas as pd
class ManifestDataset:
 def __init__(self,manifest_path): self.frame=pd.read_csv(manifest_path)
 def __len__(self): return len(self.frame)
