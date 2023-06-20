# Third-party
from pydantic import BaseSettings, Field


class Vars(BaseSettings):
    AWS_ACCESS_KEY: str = Field(env="AWS_ACCESS_KEY")
    AWS_SECRET_KEY: str = Field(env="AWS_SECRET_KEY")
    ACCOUNT: str = Field(env="ACCOUNT")
    USER: str = Field(env="USER")
    PASSWORD: str = Field(env="PASSWORD")
    WAREHOUSE: str = Field(env="WAREHOUSE")
    ES_USERNAME: str = Field(env="ES_USERNAME")
    ES_PASSWORD: str = Field(env="ES_PASSWORD")
    ES_ENDPOINT: str = Field(env="ES_ENDPOINT")
