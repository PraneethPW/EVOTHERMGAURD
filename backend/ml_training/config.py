from dataclasses import dataclass
@dataclass
class TrainingConfig:
    manifest_path:str="dataset/manifest.csv"; image_size:int=224; batch_size:int=16; epochs:int=30; learning_rate:float=3e-4; patience:int=5
