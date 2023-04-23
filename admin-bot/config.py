# Third-party
from typing import Dict

from pydantic import BaseSettings, Field


class Vars(BaseSettings):
    key: str = Field(env="TOKEN")
    app_token: str = Field(env="APP_KEY")
    admin_list_var: str = Field(env="ADMIN_LIST")
    return_account: str = Field(env="RETURN_ACCOUNT")
    change_status: str = Field(env="CHANGE_STATUS")
    suspend_activate: str = Field(env="SUSPEND_ACTIVATE")
    extend_poc: str = Field(env="EXTEND_POC")
    change_tier: str = Field(env="CHANGE_TIER")








