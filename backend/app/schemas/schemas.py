from pydantic import BaseModel, EmailStr, Field, HttpUrl
from app.schemas.common import ORMModel
class RegisterIn(BaseModel): name: str=Field(min_length=2,max_length=120); email: EmailStr; password: str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel): email: EmailStr; password: str
class UserOut(ORMModel): id:str; name:str; email:EmailStr
class TokenOut(BaseModel): access_token:str; token_type:str="bearer"; user:UserOut
class EquipmentIn(BaseModel): equipment_name:str; equipment_type:str; asset_code:str|None=None; location_label:str|None=None; manufacturer:str|None=None; notes:str|None=None
class EquipmentOut(ORMModel): id:str; equipment_name:str; equipment_type:str; asset_code:str|None=None; location_label:str|None=None; manufacturer:str|None=None; notes:str|None=None
class InspectionIn(BaseModel): equipment_id:str; ambient_temperature:float=Field(ge=-80,le=100); humidity:float=Field(ge=0,le=100); weather:str; season:str; time_of_day:str; sun_exposure:str|None=None; notes:str|None=None
class FeedbackIn(BaseModel): operator_status:str; actual_issue:str|None=None; action_taken:str; notes:str|None=None; verified:bool=False
class MonitoringSourceIn(BaseModel):
    equipment_id: str
    station_name: str = Field(min_length=2,max_length=180)
    latitude: float = Field(ge=-90,le=90)
    longitude: float = Field(ge=-180,le=180)
    rgb_camera_url: HttpUrl
    thermal_camera_url: HttpUrl
    monitoring_enabled: bool = True
class MonitoringSourceUpdate(BaseModel):
    station_name: str|None = Field(default=None,min_length=2,max_length=180)
    latitude: float|None = Field(default=None,ge=-90,le=90)
    longitude: float|None = Field(default=None,ge=-180,le=180)
    rgb_camera_url: HttpUrl|None = None
    thermal_camera_url: HttpUrl|None = None
    monitoring_enabled: bool|None = None
