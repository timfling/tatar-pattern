from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Credentials(Input):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator('email')
    @classmethod
    def normalize(cls, value):
        return str(value).lower()

class Profile(Input):
    firstName: str = Field(default='', max_length=80)
    lastName: str = Field(default='', max_length=80)
    occupation: Literal['', 'designer', 'artist', 'student', 'researcher', 'other'] = ''
    avatar: str | None = Field(default=None, max_length=12000, pattern=r'^data:image/jpeg;base64,[A-Za-z0-9+/=]+$')

class Registration(Credentials, Profile):
    firstName: str = Field(default='', max_length=80)
    lastName: str = Field(default='', max_length=80)

    @field_validator('firstName', 'lastName')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Введите имя и фамилию')
        return value.strip()

class Selections(Input):
    style: Literal['heritage','modern','porcelain-sign','leather-mosaic','festive']
    composition: Literal['medallion','border','rapport']
    parameters: Literal['default','sparse','dense'] = 'default'
    motifs: list[str] = Field(default_factory=list,max_length=16)
    elementCodes: list[str] = Field(default_factory=list,max_length=16)
    scale: float = Field(default=1.0,ge=0.3,le=2.0)
    transparentBackground: bool = False
    backgroundColor: str | None = Field(default=None,pattern=r'^#[0-9a-fA-F]{6}$')
    renderer: Literal['legacy','composition-v1'] = 'legacy'
    rapportOutput: Literal['module','sample'] = 'module'
    moduleSize: tuple[int, int] | None = None
    outputSize: tuple[int, int] | None = None
    colorMode: Literal['original','silhouette'] = 'original'
    palette: Literal['emerald','porcelain','leather']
    usage: Literal['architecture','textile','packaging','interior','web']

    @field_validator('moduleSize')
    @classmethod
    def bounded_module(cls, value):
        if value is not None and any(v < 256 or v > 2048 for v in value):
            raise ValueError('Стороны модуля должны быть 256–2048 px')
        return value

    @field_validator('outputSize')
    @classmethod
    def allowed_size(cls, value):
        allowed = {(1024,1024),(900,1200),(800,1200),(720,1280)}
        allowed |= {(h,w) for w,h in allowed}
        if value is not None and value not in allowed:
            raise ValueError('Выберите один из поддерживаемых форматов')
        return value

    @field_validator('motifs','elementCodes')
    @classmethod
    def distinct(cls, value):
        if any(not v.strip() or len(v)>100 for v in value):
            raise ValueError('Нужны непустые ключи длиной до 100 символов')
        if len(set(value)) != len(value):
            raise ValueError('Мотивы не должны повторяться')
        return value

Identifier = str

class Generate(Input):
    mode: Literal['flat','ai'] = 'flat'
    seed: int = Field(default=0,ge=0,le=2147483647)
    selections: Selections
    prompt: str = Field(default='', max_length=2000)
    projectId: str | None = Field(default=None, pattern=r'^[1-9][0-9]{0,17}$')

class Project(Input):
    title: str = Field(min_length=1,max_length=120)
    @field_validator('title')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Название не должно быть пустым')
        return value.strip()

class PatchGeneration(Input):
    title: str | None = Field(default=None, min_length=1,max_length=120)
    rating: Literal['like','dislike'] | None = None
    projectId: str | None = Field(default=None, pattern=r'^[1-9][0-9]{0,17}$')
    @field_validator('title')
    @classmethod
    def nonempty(cls, value):
        if value is None or not value.strip():
            raise ValueError('Название не должно быть пустым')
        return value.strip()
