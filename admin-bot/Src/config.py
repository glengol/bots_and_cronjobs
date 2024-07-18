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
    extend_poc_7_days: str = Field(env="EXTEND_POC_7_DAYS")
    extend_poc_2_days: str = Field(env="EXTEND_POC_2_DAYS")
    change_tier: str = Field(env="CHANGE_TIER")
    trial_started_last_7_days: str = Field(env="TRIAL_STARTED_LAST_7_DAYS")
    trial_about_end: str = Field(env="TRIAL_ABOUT_END")
    trial_in_progress: str = Field(env="TRIAL_IN_PROGRESS")
    get_id: str = Field(env="GET_ID")








