from pydantic import BaseModel, EmailStr, Field
from app.schemas.common import ORMModel
class RegisterIn(BaseModel): name: str=Field(min_length=2,max_length=120); email: EmailStr; password: str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel): email: EmailStr; password: str
class UserOut(ORMModel): id:str; name:str; email:EmailStr
class TokenOut(BaseModel): access_token:str; token_type:str="bearer"; user:UserOut
class EquipmentIn(BaseModel): equipment_name:str; equipment_type:str; asset_code:str|None=None; location_label:str|None=None; manufacturer:str|None=None; notes:str|None=None
class EquipmentOut(ORMModel): id:str; equipment_name:str; equipment_type:str; asset_code:str|None=None; location_label:str|None=None; manufacturer:str|None=None; notes:str|None=None
class InspectionIn(BaseModel): equipment_id:str; ambient_temperature:float=Field(ge=-80,le=100); humidity:float=Field(ge=0,le=100); weather:str; season:str; time_of_day:str; sun_exposure:str|None=None; notes:str|None=None
class FeedbackIn(BaseModel): operator_status:str; actual_issue:str|None=None; action_taken:str; notes:str|None=None; verified:bool=False
